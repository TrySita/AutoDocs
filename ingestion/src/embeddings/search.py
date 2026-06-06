"""Semantic search processor combining vector ANN and FTS queries.

Provides:
- Vector search using sqlite-vec over the `embeddings_vec` virtual table
- FTS search over definition names (`definitions_name_fts`)
- FTS search over file paths (`files_path_fts`)

Designed to be lightweight and rely on DatabaseManager helpers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, cast
from sqlalchemy import text

from database.manager import DatabaseManager
from embeddings.openai_client import EmbeddingsClient


SearchEntity = Literal["file", "definition"]

# Reciprocal-rank-fusion damping constant. 60 is the value from the original
# RRF paper (Cormack et al.) and the de-facto default; it limits how much any
# single result list can dominate the fused ranking.
RRF_K = 60


@dataclass
class SemanticSearchProcessor:
    db: DatabaseManager
    embedder: EmbeddingsClient | None = None
    RRF_K: int = RRF_K

    def embed_query(self, query: str) -> list[float]:
        if not self.embedder:
            raise RuntimeError("Embedder not configured for semantic search")
        return self.embedder.embed_single(query)

    def vector_search(
        self, query: str, top_k: int = 10, entity_type: SearchEntity | None = None
    ) -> list[dict[str, Any]]:
        """Nearest neighbor search using sqlite-vec and the embeddings table."""
        vec = self.embed_query(query)
        return self.db.query_nearest_neighbors(
            vec, top_k=top_k, entity_type=entity_type
        )

    def fts_definitions(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search definitions by name using FTS5."""
        sql = (
            "SELECT d.id AS entity_id, d.name AS entity_name, f.file_path, f.language,"
            " 'definition' AS entity_type, bm25(definitions_name_fts) AS rank, d.ai_summary, d.created_at "
            "FROM definitions_name_fts JOIN definitions d ON d.id = definitions_name_fts.rowid "
            "JOIN files f ON f.id = d.file_id "
            "WHERE definitions_name_fts MATCH :q ORDER BY rank LIMIT :k"
        )
        with self.db.get_session() as session:
            result = session.execute(text(sql), {"q": query, "k": top_k})
            cols = result.keys()
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
            # Normalize naming to include distance-like measure for consistency
            for r in rows:
                r["distance"] = float(r.pop("rank"))
            return rows

    def fts_files(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Search file paths using FTS5."""
        sql = (
            "SELECT f.id AS entity_id, f.file_path AS entity_name, f.file_path, f.language,"
            " 'file' AS entity_type, bm25(files_path_fts) AS rank, f.ai_summary, f.created_at "
            "FROM files_path_fts JOIN files f ON f.id = files_path_fts.rowid "
            "WHERE files_path_fts MATCH :q ORDER BY rank LIMIT :k"
        )
        with self.db.get_session() as session:
            result = session.execute(text(sql), {"q": query, "k": top_k})
            cols = result.keys()
            rows = [dict(zip(cols, row)) for row in result.fetchall()]
            for r in rows:
                r["distance"] = float(r.pop("rank"))
            return rows

    def hybrid_search(self, query: str, top_k: int = 10) -> list[dict[str, Any]]:
        """Combine vector + FTS results via reciprocal-rank fusion (RRF).

        The three retrievers produce incomparable scores: sqlite-vec returns L2
        distances (smaller is better, non-negative) while FTS5 returns bm25
        scores (more negative is better). Sorting them together by raw value is
        meaningless. Instead each result is scored by its *rank* within its own
        list and the per-list contributions are summed:

            score = sum_over_lists( 1 / (RRF_K + rank) )

        where ``rank`` is 1-based and ``RRF_K`` dampens the influence of any
        single list (the standard constant is 60). An item that ranks well in
        several lists therefore beats an item that ranks well in only one.
        The fused score is attached as ``score`` and results are sorted by it
        (descending), deduplicated by ``(entity_type, entity_id)``.

        Only the vector list yields a comparable ``distance`` (an L2 distance
        that downstream code converts to a similarity). FTS lists carry bm25
        scores, which are *not* L2 distances, so they must never surface as a
        ``distance``: the fused row keeps the vector distance whenever the
        entity appeared in the vector list, and genuinely FTS-only rows carry no
        ``distance`` key at all.
        """
        # Vector portion (if embedder configured). Captured separately so its L2
        # distance can be reattached to fused rows regardless of which list was
        # enumerated first during fusion.
        vector_results: list[dict[str, Any]] = []
        if self.embedder:
            vector_results = self.vector_search(query, top_k=top_k, entity_type=None)

        # FTS portions
        ranked_lists: list[list[dict[str, Any]]] = [
            vector_results,
            self.fts_definitions(query, top_k=top_k),
            self.fts_files(query, top_k=top_k),
        ]

        def _key(r: dict[str, Any]) -> tuple[str, int]:
            return (
                cast(str, r.get("entity_type")),
                int(cast(str, r.get("entity_id"))),
            )

        # The only honest distance is the vector L2 distance.
        vector_distances: dict[tuple[str, int], float] = {
            _key(r): cast(float, r["distance"])
            for r in vector_results
            if r.get("distance") is not None
        }

        fused: dict[tuple[str, int], dict[str, Any]] = {}
        for ranked in ranked_lists:
            for position, r in enumerate(ranked):
                key = _key(r)
                contribution = 1.0 / (self.RRF_K + position + 1)
                existing = fused.get(key)
                if existing is None:
                    # Keep the first-seen row's metadata; track the fused score.
                    merged_row = dict(r)
                    merged_row["score"] = contribution
                    fused[key] = merged_row
                else:
                    existing["score"] += contribution

        # Reconcile distance: vector L2 distance if available, otherwise drop the
        # bm25 value an FTS list may have left so it cannot masquerade as one.
        for key, row in fused.items():
            vector_distance = vector_distances.get(key)
            if vector_distance is not None:
                row["distance"] = vector_distance
            else:
                row.pop("distance", None)

        merged = list(fused.values())
        merged.sort(key=lambda x: x["score"], reverse=True)
        return merged[:top_k]
