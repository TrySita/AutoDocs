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


@dataclass
class SemanticSearchProcessor:
    db: DatabaseManager
    embedder: EmbeddingsClient | None = None

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
        """Combine vector + FTS results. Lightweight merging.

        Strategy: concatenate NN results (both entity types) and FTS matches for
        definitions and files; then deduplicate by (entity_type, entity_id)
        keeping the lowest distance.
        """
        results: list[dict[str, Any]] = []

        # Vector portions (if embedder configured)
        if self.embedder:
            results.extend(self.vector_search(query, top_k=top_k, entity_type=None))

        # FTS portions
        results.extend(self.fts_definitions(query, top_k=top_k))
        results.extend(self.fts_files(query, top_k=top_k))

        # Deduplicate and keep best (lowest distance)
        best: dict[tuple[str, int], dict[str, Any]] = {}
        for r in results:
            key: tuple[str, int] = (
                cast(str, r.get("entity_type")),
                int(cast(str, r.get("entity_id"))),
            )
            if key not in best or r.get("distance", 1e9) < best[key].get(
                "distance", 1e9
            ):
                best[key] = r

        merged = list(best.values())
        merged.sort(key=lambda x: x.get("distance", 0.0))
        return merged[:top_k]
