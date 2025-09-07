"""Ingestion job worker.

Implements the full ingestion pipeline:
- Shallow clone public repo
- Provision Turso DB + auth token; connect via embedded replica
- Hybrid parse (no debug artifacts), collect delta
- Summaries (full or incremental)
- Embeddings (full or targeted upsert)
- Finalize: best‑effort sync, dispose, cleanup
"""

from __future__ import annotations

import asyncio
from copy import copy
import logging
import os
from dataclasses import dataclass
from pathlib import Path
import shutil
from types import NoneType
from typing import Final

from api.job_manager import JobResult, update_progress
from api.schemas import JobProgress
from api.schemas import IngestRequest
from ast_parsing.utils.git_utils import ensure_shallow_main
from dag_builder.netx import DAGBuilder
from database.manager import DatabaseManager, session_scope
from database.types import ParseDelta
from ast_parsing.hybrid_parser import HybridParser
from ast_parsing.parser import get_parser
from ai_analysis.parallel_summaries import ParallelSummaryExecutor
from embeddings.openai_client import EmbeddingsClient
from embeddings.generator import EmbeddingsGenerator
from database.models import FileModel, DefinitionModel, RepositoryModel

# Set up logger
logger = logging.getLogger(__name__)

PHASES: Final[list[str]] = [
    "clone",
    "parse",
    "summaries",
    "embeddings",
    "finalize",
]


@dataclass
class IngestSettings:
    github_url: str
    branch: str | None
    force_full: bool
    repo_slug: str


def _extract_changed_ids(
    delta: ParseDelta, db: DatabaseManager
) -> tuple[list[int], list[int]]:
    """Get (changed_file_ids, changed_definition_ids) from delta."""
    file_ids: list[int] = []
    def_ids: list[int] = list(delta.definitions_added)

    paths: set[str] = set()
    paths.update(delta.files_added)
    paths.update(delta.files_modified)
    paths.update([r.new for r in delta.files_renamed])

    if paths:
        from database.models import FileModel  # local import to avoid cycles

        with db.get_session() as session:
            rows = (
                session.query(FileModel.id)
                .filter(FileModel.file_path.in_(list(paths)))
                .all()
            )
            file_ids = [i for (i,) in rows]

    return file_ids, def_ids


async def run_ingest_job(job_id: str, payload: IngestRequest) -> JobResult:
    """Background worker entrypoint for ingestion jobs.

    The payload is the dict form of IngestRequest (validated by FastAPI).
    """
    WORKDIR = Path(os.getenv("ANALYSIS_DB_DIR", "."))

    counters: dict[str, int] = {
        "files_processed": 0,
        "definitions_processed": 0,
        "summaries_generated_files": 0,
        "summaries_generated_definitions": 0,
        "embeddings_upserted_files": 0,
        "embeddings_upserted_definitions": 0,
    }
    warnings: list[str] = []

    settings = copy(payload)
    logger.info(
        f"[{job_id}] Parsed settings: force_full={settings.force_full}, branch={settings.branch}"
    )

    repo: RepositoryModel | None = None
    repo_path = WORKDIR / "clones" / settings.repo_slug

    logger.info(f"[{job_id}] Starting clone phase")
    update_progress(job_id, JobProgress.cloning_repo)
    repo_info = ensure_shallow_main(
        repo_path=repo_path.as_posix(), remote_url=settings.github_url
    )

    local_db = DatabaseManager(db_path=str(WORKDIR / f"{settings.repo_slug}.db"))

    # persist repo info to database
    with session_scope(local_db) as session:
        repo = (
            session.query(RepositoryModel)
            .filter_by(repo_slug=settings.repo_slug)
            .first()
        )
        if not repo:
            repo = RepositoryModel(
                remote_origin_url=settings.github_url, repo_slug=settings.repo_slug
            )
            session.add(repo)
            session.flush()  # get ID
        repo.default_branch = repo_info.default_branch

    logger.info(
        f"[{job_id}] Cloned repo to {repo_path}, commit: {repo_info.commit_hash}"
    )

    # Phase: parse
    logger.info(f"[{job_id}] Starting parse phase")
    update_progress(job_id, JobProgress.parse)

    parser = HybridParser(local_db)
    # Perform hybrid parse; HybridParser internally uses AST parser which tracks delta
    with session_scope(local_db) as session:
        repo = (
            session.query(RepositoryModel)
            .filter_by(remote_origin_url=settings.github_url)
            .first()
        )

        _ = await parser.parse_repository(
            session=session,
            repo_path=str(repo_path),
            repository=repo,
            new_commit_hash=repo_info.commit_hash,
        )

    # Extract delta from the underlying AST parser
    delta: ParseDelta | None = get_parser(db_manager=local_db).current_delta  # type: ignore[arg-type]
    if delta:
        logger.info(
            f"[{job_id}] Parse delta: {len(delta.files_added)} files added, {len(delta.files_modified)} modified, {len(delta.definitions_added)} definitions added"
        )
    else:
        logger.info(f"[{job_id}] No parse delta available")

    mode = "full"

    dag_builder = DAGBuilder(db_manager=local_db)
    logger.info(f"[{job_id}] Building file dependency graph")
    definition_graph = dag_builder.build_function_dependency_graph()
    file_graph = dag_builder.build_file_dependency_graph(definition_graph)

    logger.info(
        f"[{job_id}] File dependency graph: {file_graph.number_of_nodes()} nodes, {file_graph.number_of_edges()} edges"
    )

    # Phase: summaries
    logger.info(f"[{job_id}] Starting summaries phase")
    update_progress(job_id, JobProgress.summaries)
    executor = ParallelSummaryExecutor(db_manager=local_db)

    if not settings.force_full and delta is not None:
        # Consider incremental if any changes are detected
        has_file_changes = bool(
            delta.files_added or delta.files_modified or delta.files_renamed
        )
        has_def_changes = bool(delta.definitions_added)
        if has_file_changes or has_def_changes:
            mode = "incremental"

    logger.info(f"[{job_id}] Summary mode: {mode}")

    if mode == "incremental" and delta is not None:
        stats = await executor.generate_incremental_summaries(delta)
        # Approximate counters from stats
        counters["summaries_generated_definitions"] = stats.get("defs_in_graph", 0)  # pyright: ignore[reportAny]
        counters["summaries_generated_files"] = stats.get("files_in_graph", 0)  # pyright: ignore[reportAny]
    else:
        mode = "full"
        stats = await executor.generate_all_summaries_parallel(
            definition_graph, file_graph
        )
        counters["summaries_generated_definitions"] = stats.get("total_definitions", 0)  # pyright: ignore[reportAny]
        counters["summaries_generated_files"] = stats.get("total_files", 0)  # pyright: ignore[reportAny]

    logger.info(
        f"[{job_id}] Summaries generated: {counters['summaries_generated_files']} files, {counters['summaries_generated_definitions']} definitions"
    )

    # Phase: embeddings (local sqlite-vec)
    logger.info(f"[{job_id}] Starting embeddings phase")
    update_progress(job_id, JobProgress.embeddings)
    embeddings_api_key = os.getenv("EMBEDDINGS_API_KEY")

    embedder = EmbeddingsClient(api_key=embeddings_api_key)
    generator = EmbeddingsGenerator(
        db_manager=local_db,
        embedder=embedder,
        embedding_dims=embedder.get_embedding_dimensions(),
    )

    if mode == "incremental" and delta is not None:
        file_ids, def_ids = _extract_changed_ids(delta, local_db)
        if file_ids:
            count_files = await generator.generate_embeddings_for_files_async(file_ids)
            counters["embeddings_upserted_files"] = count_files
        if def_ids:
            count_defs = await generator.generate_embeddings_for_definitions_async(
                def_ids
            )
            counters["embeddings_upserted_definitions"] = count_defs
        logger.info(
            f"[{job_id}] Incremental embeddings: {len(file_ids)} files, {len(def_ids)} definitions"
        )
    else:
        emb_stats = await generator.generate_all_embeddings_async()
        counters["embeddings_upserted_files"] = emb_stats.get("files_processed", 0)
        counters["embeddings_upserted_definitions"] = emb_stats.get(
            "definitions_processed", 0
        )
        logger.info(
            f"[{job_id}] Full embeddings: {counters['embeddings_upserted_files']} files, {counters['embeddings_upserted_definitions']} definitions"
        )

    # Phase: finalize
    logger.info(f"[{job_id}] Starting finalize phase")
    update_progress(job_id, JobProgress.finalize)

    # Report parse counters where available
    # Count files/definitions from DB after parse
    try:
        with local_db.get_session() as session:
            counters["files_processed"] = session.query(FileModel).count()
            counters["definitions_processed"] = session.query(DefinitionModel).count()
        logger.info(
            f"[{job_id}] Final counters: {counters['files_processed']} files, {counters['definitions_processed']} definitions"
        )
    except Exception as e:
        logger.warning(f"[{job_id}] Failed to get final counters: {e}")
        # Ignore counter errors
        pass

    # Set commit hash on repository model once ingestion is complete
    with session_scope(local_db) as session:
        repo = (
            session.query(RepositoryModel)
            .filter_by(remote_origin_url=settings.github_url)
            .first()
        )
        if repo:
            repo.commit_hash = repo_info.commit_hash

    # Mask secrets; only return non-sensitive URLs and identifiers
    result = JobResult(
        mode=mode,
        commit=repo_info.commit_hash,
        counters=counters,
        warnings=warnings,
    )

    # truncate database
    local_db.close()

    logger.info(
        f"[{job_id}] Ingestion job completed successfully. Mode: {mode}, Warnings: {len(warnings)}"
    )
    return result
