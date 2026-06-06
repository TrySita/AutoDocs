"""Regression tests for embeddings bugs 5, 11, and 20 (embeddings half).

These tests do not hit the network or require API keys. The embedding/LLM
clients are stubbed, and the database session is faked so that we exercise the
pure ranking/joining/retry logic in isolation.

- Bug 5: hybrid_search must fuse the three result lists by rank (RRF), not by
  sorting incomparable raw scores (L2 distance vs. bm25) in one min-sort.
- Bug 11: _upsert_batch_async must mirror each packed vector to the row id that
  matches its (entity_type, entity_id) key, not by positional zip against the
  RETURNING rows (whose order is not guaranteed).
- Bug 20: the retry decorators in openai_client.embed and
  generator._embed_texts_async must retry only transient API/network errors,
  never non-transient errors such as authentication or validation failures.
"""

from __future__ import annotations

import asyncio
from array import array
from typing import Any

import openai
import pytest

from embeddings.generator import EmbeddingsGenerator
from embeddings.openai_client import EmbeddingsClient
from embeddings.search import SemanticSearchProcessor


# ---------------------------------------------------------------------------
# Bug 5 — hybrid_search reciprocal-rank fusion
# ---------------------------------------------------------------------------


class _StubProcessor(SemanticSearchProcessor):
    """SemanticSearchProcessor whose three retrievers return canned lists."""

    def __init__(
        self,
        vector: list[dict[str, Any]],
        fts_defs: list[dict[str, Any]],
        fts_files: list[dict[str, Any]],
    ) -> None:
        # Bypass the dataclass __init__ entirely; we only test the fusion logic.
        self._vector = vector
        self._fts_defs = fts_defs
        self._fts_files = fts_files
        # Pretend an embedder is configured so the vector branch runs.
        self.embedder = object()  # type: ignore[assignment]
        self.db = None  # type: ignore[assignment]

    def vector_search(self, query, top_k=10, entity_type=None):  # type: ignore[override]
        return self._vector[:top_k]

    def fts_definitions(self, query, top_k=10):  # type: ignore[override]
        return self._fts_defs[:top_k]

    def fts_files(self, query, top_k=10):  # type: ignore[override]
        return self._fts_files[:top_k]


def _result(entity_type: str, entity_id: int, distance: float) -> dict[str, Any]:
    return {
        "entity_type": entity_type,
        "entity_id": entity_id,
        "entity_name": f"{entity_type}-{entity_id}",
        "distance": distance,
    }


def test_hybrid_search_fuses_by_rank_not_raw_score():
    """An item ranked highly across multiple lists must beat single-list winners.

    The naive bug sorts by raw `distance`. bm25 scores from FTS are negative,
    so an FTS-only definition (distance ~ -8.0) always sorts ahead of a
    consensus item that ranks #1 in vectors (small positive L2 distance) and
    #2 in FTS. With reciprocal-rank fusion, the consensus item must win.
    """
    consensus = _result("definition", 1, distance=0.10)  # vector #1, fts def #2
    fts_only = _result("definition", 2, distance=-8.0)  # fts def #1 only

    proc = _StubProcessor(
        vector=[consensus, _result("file", 9, distance=0.20)],
        fts_defs=[fts_only, dict(consensus, distance=-7.0)],
        fts_files=[_result("file", 9, distance=-6.0)],
    )

    merged = proc.hybrid_search("q", top_k=5)

    # Deduplicated by (entity_type, entity_id).
    keys = [(r["entity_type"], r["entity_id"]) for r in merged]
    assert keys.count(("definition", 1)) == 1

    consensus_idx = keys.index(("definition", 1))
    fts_only_idx = keys.index(("definition", 2))
    assert consensus_idx < fts_only_idx, (
        "consensus item (top of two lists) must rank above the FTS-only item; "
        f"got order {keys}"
    )


def test_hybrid_search_fts_first_row_keeps_vector_distance():
    """A row seen first via FTS but also in the vector list keeps vector distance.

    RRF fuses by rank, but the *distance* carried onto the fused row drives the
    similarity score in api/main.py (it converts an L2 distance to a similarity).
    bm25 scores from FTS are not comparable to L2 distances, so the honest value
    to keep is the vector distance whenever the entity appeared in the vector
    list -- regardless of which list happened to be enumerated first.
    """
    vec_distance = 0.10
    # FTS lists are enumerated before vector here, so the entity is FTS-first.
    proc = _StubProcessor(
        vector=[_result("definition", 1, distance=vec_distance)],
        fts_defs=[_result("definition", 1, distance=-7.0)],
        fts_files=[],
    )

    merged = proc.hybrid_search("q", top_k=5)
    keys = [(r["entity_type"], r["entity_id"]) for r in merged]
    row = merged[keys.index(("definition", 1))]
    assert row["distance"] == vec_distance, (
        "fused row must carry the vector distance, not the bm25 FTS rank; "
        f"got {row.get('distance')}"
    )


def test_hybrid_search_fts_only_row_has_no_vector_distance():
    """A genuinely FTS-only row must not expose a bm25 score as a distance.

    bm25 ranks are not L2 distances; surfacing one as `distance` would make
    api/main.py report a misleading similarity. FTS-only rows therefore carry
    no `distance` key.
    """
    proc = _StubProcessor(
        vector=[_result("definition", 1, distance=0.10)],
        fts_defs=[_result("definition", 2, distance=-7.0)],
        fts_files=[],
    )

    merged = proc.hybrid_search("q", top_k=5)
    keys = [(r["entity_type"], r["entity_id"]) for r in merged]
    fts_only = merged[keys.index(("definition", 2))]
    assert "distance" not in fts_only or fts_only["distance"] is None, (
        "FTS-only row must not carry a bm25 score as a vector distance; "
        f"got {fts_only.get('distance')}"
    )


def test_hybrid_search_assigns_fusion_score_and_orders_by_it():
    """Items appearing in more lists accumulate higher RRF score."""
    a = _result("file", 1, distance=0.0)
    b = _result("file", 2, distance=0.0)

    # `a` appears #1 in all three lists; `b` appears only once at #1.
    proc = _StubProcessor(
        vector=[a, b],
        fts_defs=[a],
        fts_files=[a],
    )

    merged = proc.hybrid_search("q", top_k=5)
    keys = [(r["entity_type"], r["entity_id"]) for r in merged]
    assert keys[0] == ("file", 1)
    # The multi-list item must carry a strictly higher fusion score.
    assert merged[0]["score"] > merged[1]["score"]


# ---------------------------------------------------------------------------
# Bug 11 — _upsert_batch_async must join RETURNING rows on entity keys
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self._rows = rows

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self._rows


class _FakeSession:
    """Records the parameters of the embeddings_vec mirror insert."""

    def __init__(self, returning_rows: list[tuple[Any, ...]]) -> None:
        self._returning_rows = returning_rows
        self.mirror_params: list[dict[str, Any]] | None = None

    def __enter__(self) -> _FakeSession:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def execute(self, stmt: Any, params: Any = None) -> _FakeResult:
        # First call is the upsert (a SQLAlchemy Insert); second is the mirror
        # INSERT (a TextClause with a list of param dicts).
        if params is not None:
            self.mirror_params = params
            return _FakeResult([])
        return _FakeResult(self._returning_rows)


class _FakeDBManager:
    def __init__(self, returning_rows: list[tuple[Any, ...]]) -> None:
        self._session = _FakeSession(returning_rows)

    def create_vector_indexes(self, dims: int) -> None:
        return None

    def get_session(self) -> _FakeSession:
        return self._session


class _StubEmbedder:
    model = "stub-model"

    def __init__(self, vectors: list[list[float]]) -> None:
        self._vectors = vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._vectors


def test_upsert_mirrors_vectors_by_entity_key_not_position():
    """RETURNING rows in a different order must not misattach vectors.

    Two input rows produce two distinct vectors. The DB returns the RETURNING
    rows in REVERSE order. The positional-zip bug would attach row[0]'s id to
    the first vector, swapping them. The correct join on (entity_type,
    entity_id) attaches each vector to the row id with the matching key.
    """
    vec_a = [1.0] * 4
    vec_b = [2.0] * 4
    packed_a = array("f", vec_a).tobytes()
    packed_b = array("f", vec_b).tobytes()

    rows = [
        {
            "page_content": "summary A",
            "meta": {
                "entity_type": "file",
                "entity_id": 10,
                "entity_name": "a.py",
                "file_path": "a.py",
                "language": "python",
                "definition_type": None,
            },
        },
        {
            "page_content": "summary B",
            "meta": {
                "entity_type": "file",
                "entity_id": 20,
                "entity_name": "b.py",
                "file_path": "b.py",
                "language": "python",
                "definition_type": None,
            },
        },
    ]

    # RETURNING gives (id, entity_type, entity_id). DB returns reversed order:
    # id=200 -> entity 20 first, then id=100 -> entity 10.
    returning_rows = [
        (200, "file", 20),
        (100, "file", 10),
    ]

    db = _FakeDBManager(returning_rows)
    gen = EmbeddingsGenerator(
        db_manager=db,  # type: ignore[arg-type]
        embedder=_StubEmbedder([vec_a, vec_b]),  # type: ignore[arg-type]
        embedding_dims=4,
    )

    asyncio.run(gen._upsert_batch_async(rows))

    mirror = db._session.mirror_params
    assert mirror is not None
    by_id = {p["id"]: p["embedding"] for p in mirror}
    # Entity 10 -> id 100 must carry vec_a; entity 20 -> id 200 must carry vec_b.
    assert by_id[100] == packed_a
    assert by_id[200] == packed_b


# ---------------------------------------------------------------------------
# Bug 20 — retry only transient errors (embeddings half)
# ---------------------------------------------------------------------------


def _make_client() -> EmbeddingsClient:
    return EmbeddingsClient(api_key="test-key", embedding_dims=4)


def test_embed_does_not_retry_non_transient_error():
    """A non-transient error (auth/validation) must surface on the first call."""
    client = _make_client()
    calls = {"n": 0}

    class _BoomClient:
        class embeddings:  # noqa: N801 - mirror openai client shape
            @staticmethod
            def create(**_kwargs: Any) -> Any:
                calls["n"] += 1
                raise openai.AuthenticationError.__new__(openai.AuthenticationError)

    client.client = _BoomClient()  # type: ignore[assignment]

    with pytest.raises(openai.AuthenticationError):
        client.embed(["hello"])
    assert calls["n"] == 1, "non-transient error must not be retried"


def test_embed_retries_transient_error_then_succeeds():
    """A transient error (APIConnectionError) must be retried."""
    client = _make_client()
    calls = {"n": 0}

    class _EmbObj:
        embedding = [0.0, 0.0, 0.0, 0.0]

    class _Resp:
        data = [_EmbObj()]

    class _FlakyClient:
        class embeddings:  # noqa: N801
            @staticmethod
            def create(**_kwargs: Any) -> Any:
                calls["n"] += 1
                if calls["n"] < 2:
                    raise openai.APIConnectionError(request=None)  # type: ignore[arg-type]
                return _Resp()

    client.client = _FlakyClient()  # type: ignore[assignment]

    # Speed up the wait between attempts for the test.
    client.embed.retry.sleep = lambda _s: None  # type: ignore[attr-defined]

    out = client.embed(["hello"])
    assert calls["n"] == 2
    assert out == [[0.0, 0.0, 0.0, 0.0]]


def test_generator_embed_async_does_not_retry_non_transient():
    """generator._embed_texts_async must not retry a non-transient error."""
    calls = {"n": 0}

    class _BoomEmbedder:
        model = "stub"

        def embed(self, _texts: list[str]) -> list[list[float]]:
            calls["n"] += 1
            raise ValueError("bad request, not transient")

    gen = EmbeddingsGenerator(
        db_manager=_FakeDBManager([]),  # type: ignore[arg-type]
        embedder=_BoomEmbedder(),  # type: ignore[arg-type]
        embedding_dims=4,
    )

    with pytest.raises(ValueError):
        asyncio.run(gen._embed_texts_async(["x"]))
    assert calls["n"] == 1, "non-transient error must not be retried"
