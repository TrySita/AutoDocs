"""
Embeddings generator using a managed embedder (e.g., Gemini) and
local SQLite with sqlite-vec for storage and retrieval.

- Reads summaries from your existing `files` / `definitions` tables
- Stores embeddings and metadata in a normal SQL table (`embeddings`)
- Mirrors vectors into a sqlite-vec virtual table (`embeddings_vec`) for ANN search
- Upserts are idempotent using (entity_type, entity_id) unique constraint

Usage:
    generator = EmbeddingsGenerator(
        db_manager=my_db_manager,
        embedder=my_gemini_client,        # must implement .embed(List[str]) -> List[List[float]]
        embedding_dims=1536,
    )
    stats = generator.generate_all_embeddings(batch_size=100)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Iterator
from typing import Any
from array import array

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from database.manager import DatabaseManager
from database.models import FileModel, DefinitionModel, EmbeddingModel
from .models import EmbeddingMetadata
from .openai_client import EmbeddingsClient

logger = logging.getLogger(__name__)


@dataclass
class EmbeddingsGenerator:
    db_manager: DatabaseManager
    embedder: EmbeddingsClient
    embedding_dims: int = 1536
    skip_existing: bool = True
    max_concurrent: int = 4
    max_requests_per_minute: int = 3000
    min_batch_size: int = 100

    def __post_init__(self):
        """Ensure sqlite-vec virtual table exists for the configured dimensions."""
        try:
            # Best-effort creation; DatabaseManager also attempts this at startup
            self.db_manager.create_vector_indexes(self.embedding_dims)
            logger.info(
                f"sqlite-vec configured: virtual table 'embeddings_vec' with dims={self.embedding_dims}"
            )
        except Exception as e:  # pragma: no cover - best effort
            logger.warning(f"Unable to ensure sqlite-vec table: {e}")

    def _iter_file_rows(self, session: Session) -> Iterator[dict[str, Any]]:
        """Yield rows (content + tiny metadata) for FILE summaries."""
        # First get total count of files with summaries
        total_files_with_summaries = (
            session.query(FileModel)
            .filter(FileModel.ai_summary.isnot(None))
            .filter(FileModel.ai_summary != "")
            .count()
        )

        q = (
            session.query(FileModel)
            .filter(FileModel.ai_summary.isnot(None))
            .filter(FileModel.ai_summary != "")
        )

        files = q.all()
        logger.info(
            "📁 Files analysis: %d total with summaries, %d queued for processing",
            total_files_with_summaries,
            len(files),
        )

        for f in files:
            meta = EmbeddingMetadata(
                entity_type="file",
                entity_id=f.id,
                entity_name=f.file_path,
                file_path=f.file_path,
                language=f.language,
            )
            yield {
                "page_content": f.ai_summary,
                "meta": {
                    "entity_type": meta.entity_type,
                    "entity_id": meta.entity_id,
                    "entity_name": meta.entity_name,
                    "file_path": meta.file_path,
                    "language": meta.language,
                    "definition_type": None,
                    "created_at": meta.created_at.isoformat(),
                },
            }

    def _iter_definition_rows(self, session: Session) -> Iterator[dict[str, Any]]:
        """Yield rows (content + tiny metadata) for DEFINITION summaries."""
        # First get total count of definitions with summaries
        total_definitions_with_summaries = (
            session.query(DefinitionModel)
            .filter(DefinitionModel.ai_summary.isnot(None))
            .filter(DefinitionModel.ai_summary != "")
            .count()
        )

        q = (
            session.query(DefinitionModel)
            .options(joinedload(DefinitionModel.file))
            .filter(DefinitionModel.ai_summary.isnot(None))
            .filter(DefinitionModel.ai_summary != "")
        )

        defs = q.all()
        logger.info(
            "🔧 Definitions analysis: %d total with summaries, %d queued for processing",
            total_definitions_with_summaries,
            len(defs),
        )

        for d in defs:
            meta = EmbeddingMetadata(
                entity_type="definition",
                entity_id=d.id,
                entity_name=d.name,
                file_path=d.file.file_path,
                language=d.file.language if d.file else None,
                definition_type=d.definition_type,
            )
            page_content = (
                f"{d.ai_summary}\n\nName: {d.name}\nType: {d.definition_type}"
            )
            m = meta.model_dump()
            m["created_at"] = meta.created_at.isoformat()
            yield {"page_content": page_content, "meta": m}

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=120),
        retry=retry_if_exception_type((Exception,)),
    )
    async def _embed_texts_async(self, texts: list[str]) -> list[list[float]]:
        """Async wrapper for gemini embeddings with retry logic."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.embedder.embed, texts)

    async def _upsert_batch_async(self, rows: list[dict[str, Any]]) -> None:
        """Upsert embeddings + metadata for a batch of documents into SQLite.

        - Upserts into SQL table `embeddings` via ON CONFLICT(entity_type, entity_id)
        - Mirrors vectors into sqlite-vec virtual table `embeddings_vec` (rowid=id)
        """
        if not rows:
            return

        texts = [r["page_content"] for r in rows]
        vectors = await self._embed_texts_async(texts)

        packed_vectors: list[bytes] = [array("f", vec).tobytes() for vec in vectors]

        # Prepare rows for SQL upsert
        to_upsert: list[dict[str, Any]] = []
        for r, packed in zip(rows, packed_vectors):
            m = r["meta"]
            to_upsert.append(
                {
                    "entity_type": m.get("entity_type"),
                    "entity_id": m.get("entity_id"),
                    "entity_name": m.get("entity_name"),
                    "file_path": m.get("file_path"),
                    "language": m.get("language"),
                    "definition_type": m.get("definition_type"),
                    "embedding_model": self.embedder.model,
                    "embedding_dims": self.embedding_dims,
                    "embedding": packed,
                    # Ensure NOT NULL timestamp fields are populated on insert
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
            )

        try:
            with self.db_manager.get_session() as session:
                sqlite_insert = insert(EmbeddingModel).values(to_upsert)
                stmt = sqlite_insert.on_conflict_do_update(
                    index_elements=[
                        EmbeddingModel.entity_type,
                        EmbeddingModel.entity_id,
                    ],
                    set_={
                        "entity_name": sqlite_insert.excluded.entity_name,  # type: ignore[attr-defined]
                        "file_path": sqlite_insert.excluded.file_path,  # type: ignore[attr-defined]
                        "language": sqlite_insert.excluded.language,  # type: ignore[attr-defined]
                        "definition_type": sqlite_insert.excluded.definition_type,  # type: ignore[attr-defined]
                        "embedding_model": sqlite_insert.excluded.embedding_model,  # type: ignore[attr-defined]
                        "embedding_dims": sqlite_insert.excluded.embedding_dims,  # type: ignore[attr-defined]
                        "embedding": sqlite_insert.excluded.embedding,  # type: ignore[attr-defined]
                        "updated_at": datetime.now(timezone.utc),
                    },
                ).returning(
                    EmbeddingModel.id,
                    EmbeddingModel.entity_type,
                    EmbeddingModel.entity_id,
                )

                result = session.execute(stmt)
                returned = result.fetchall()

                # Mirror into sqlite-vec virtual table (rowid=id)
                if returned:
                    # Build mapping back to packed vectors using position
                    params = []
                    for row, packed in zip(returned, packed_vectors):
                        params.append({"id": row[0], "embedding": packed})
                    _ = session.execute(
                        text(
                            "INSERT OR REPLACE INTO embeddings_vec(rowid, embedding) VALUES (:id, :embedding)"
                        ),
                        params,
                    )
        except Exception as e:
            logger.error(f"Failed to upsert batch to SQLite/sqlite-vec: {e}")
            raise

    async def _process_batches_parallel(
        self, rows: list[dict[str, Any]], entity_type: str = "items"
    ) -> None:
        """Process embedding batches in parallel with rate limiting."""
        if not rows:
            return

        batch_size = min(self.min_batch_size, len(rows))
        # Calculate delay between batches to respect rate limit
        requests_per_second = self.max_requests_per_minute / 60
        delay_between_batches = batch_size / requests_per_second

        total_batches = (len(rows) + batch_size - 1) // batch_size
        logger.info(
            f"🚀 Processing {len(rows)} {entity_type} embeddings in {total_batches} batches (batch size: {batch_size})"
        )

        sem = asyncio.Semaphore(self.max_concurrent)
        processed_count = 0

        # Process in batches
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            batch_num = i // batch_size + 1
            remaining = len(rows) - processed_count

            logger.info(
                f"📦 Batch {batch_num}/{total_batches}: Processing {len(batch)} {entity_type} ({remaining} remaining)"
            )

            async def run_batch(batch_rows: list[dict[str, Any]]) -> None:
                async with sem:
                    return await asyncio.wait_for(
                        self._upsert_batch_async(batch_rows), timeout=300
                    )

            # Execute batch
            try:
                start_time = asyncio.get_event_loop().time()
                await run_batch(batch)
                end_time = asyncio.get_event_loop().time()
                processed_count += len(batch)

                logger.info(
                    f"✅ Batch {batch_num} completed in {end_time - start_time:.1f}s ({processed_count}/{len(rows)} {entity_type} processed)"
                )

            except Exception as e:
                logger.error(f"❌ Error processing batch {batch_num}: {e}")
                raise

            # Add delay between batches (except for the last one)
            if i + batch_size < len(rows):
                logger.info(
                    f"⏳ Rate limiting: waiting {delay_between_batches:.1f}s before next batch..."
                )
                await asyncio.sleep(delay_between_batches)

        logger.info(
            f"🎉 Completed processing all {len(rows)} {entity_type} embeddings!"
        )

    async def generate_all_embeddings_async(
        self, batch_size: int = 100, files_first: bool = True
    ) -> dict[str, int]:
        """Generate embeddings for all missing file and definition summaries using async processing."""
        logger.info(
            "🚀 Starting async embeddings generation (dims=%d)...", self.embedding_dims
        )

        start_time = asyncio.get_event_loop().time()

        with self.db_manager.get_session() as session:
            file_rows = list(self._iter_file_rows(session))
            def_rows = list(self._iter_definition_rows(session))

        total_to_process = len(file_rows) + len(def_rows)
        if total_to_process == 0:
            logger.info(
                "✅ No embeddings to generate - all items are already processed!"
            )
            return {
                "files_processed": 0,
                "definitions_processed": 0,
                "total_embeddings": 0,
            }

        logger.info(
            f"📊 Overall progress: {total_to_process} total embeddings to generate ({len(file_rows)} files + {len(def_rows)} definitions)"
        )

        if files_first:
            buckets = [("files", file_rows), ("definitions", def_rows)]
        else:
            buckets = [("definitions", def_rows), ("files", file_rows)]

        for entity_type, bucket in buckets:
            if bucket:  # Only process non-empty buckets
                logger.info(f"🔄 Starting {entity_type} embedding generation...")
                await self._process_batches_parallel(bucket, entity_type)
                logger.info(f"✅ Completed {entity_type} embedding generation!")

        end_time = asyncio.get_event_loop().time()
        total_time = end_time - start_time

        logger.info(
            f"🎉 All embeddings generation completed! Total time: {total_time:.1f}s"
        )
        logger.info(
            f"📈 Performance: {total_to_process / total_time:.1f} embeddings/second"
        )

        return {
            "files_processed": len(file_rows),
            "definitions_processed": len(def_rows),
            "total_embeddings": len(file_rows) + len(def_rows),
            "processing_time_seconds": int(total_time),
        }

    def generate_all_embeddings(
        self, batch_size: int = 100, files_first: bool = True
    ) -> dict[str, int]:
        """Generate embeddings for all missing file and definition summaries (sync wrapper)."""
        return asyncio.run(self.generate_all_embeddings_async(batch_size, files_first))

    async def generate_embeddings_for_files_async(self, file_ids: list[int]) -> int:
        """Generate embeddings for specific file IDs using async processing."""
        with self.db_manager.get_session() as session:
            q = (
                session.query(FileModel)
                .filter(FileModel.id.in_(file_ids))
                .filter(FileModel.ai_summary.isnot(None))
                .filter(FileModel.ai_summary != "")
            )
            files = q.all()

        rows: list[dict[str, Any]] = []
        for f in files:
            meta = EmbeddingMetadata(
                entity_type="file",
                entity_id=f.id,
                entity_name=f.file_path,
                file_path=f.file_path,
                language=f.language,
            )
            rows.append(
                {
                    "page_content": f.ai_summary,
                    "meta": {
                        "entity_type": meta.entity_type,
                        "entity_id": meta.entity_id,
                        "entity_name": meta.entity_name,
                        "file_path": meta.file_path,
                        "language": meta.language,
                        "definition_type": None,
                        "created_at": meta.created_at.isoformat(),
                    },
                }
            )
        if rows:
            await self._process_batches_parallel(rows, "files")
        return len(rows)

    def generate_embeddings_for_files(self, file_ids: list[int]) -> int:
        """Generate embeddings for specific file IDs (sync wrapper)."""
        return asyncio.run(self.generate_embeddings_for_files_async(file_ids))

    async def generate_embeddings_for_definitions_async(
        self, definition_ids: list[int]
    ) -> int:
        """Generate embeddings for specific definition IDs using async processing."""
        with self.db_manager.get_session() as session:
            q = (
                session.query(DefinitionModel)
                .options(joinedload(DefinitionModel.file))
                .filter(DefinitionModel.id.in_(definition_ids))
                .filter(DefinitionModel.ai_summary.isnot(None))
                .filter(DefinitionModel.ai_summary != "")
            )
            defs = q.all()

        rows: list[dict[str, Any]] = []
        for d in defs:
            meta = EmbeddingMetadata(
                entity_type="definition",
                entity_id=d.id,
                entity_name=d.name,
                file_path=d.file.file_path,
                language=d.file.language,
                definition_type=d.definition_type,
            )
            rows.append(
                {
                    "page_content": d.ai_summary,
                    "meta": {
                        **meta.model_dump(),
                        "created_at": meta.created_at.isoformat(),
                    },
                }
            )
        if rows:
            await self._process_batches_parallel(rows, "definitions")
        return len(rows)

    def generate_embeddings_for_definitions(self, definition_ids: list[int]) -> int:
        """Generate embeddings for specific definition IDs (sync wrapper)."""
        return asyncio.run(
            self.generate_embeddings_for_definitions_async(definition_ids)
        )

    def get_embeddings_stats(self) -> dict[str, int]:
        """Basic counts from local embeddings table."""
        try:
            with self.db_manager.get_session() as session:
                total = session.query(EmbeddingModel).count()
                files = (
                    session.query(EmbeddingModel)
                    .filter(EmbeddingModel.entity_type == "file")
                    .count()
                )
                defs = (
                    session.query(EmbeddingModel)
                    .filter(EmbeddingModel.entity_type == "definition")
                    .count()
                )
            return {"total": total, "files": files, "definitions": defs}
        except Exception as e:
            logger.error(f"Failed to get local embeddings stats: {e}")
            return {"total": 0, "files": 0, "definitions": 0}
