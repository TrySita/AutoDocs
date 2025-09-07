"""FastAPI app exposing ingestion endpoints and job status APIs.

This API does not directly read from the analysis DB; all work happens
inside background ingestion jobs.
"""

import logging
from typing import cast
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from api.schemas import (
    IngestRequest,
    EnqueueResponse,
    JobProgress,
    JobStatus,
    JobStatusResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
    DeleteRepoRequest,
    DeleteRepoResponse,
)
from api.job_manager import submit_job, get_job
from api.ingestion import run_ingest_job
from database.manager import DatabaseManager
from embeddings.models import EmbeddingMetadata
from embeddings.search import SemanticSearchProcessor
from embeddings.openai_client import EmbeddingsClient
import os
from datetime import datetime

# Load environment for local dev first from .env and .env.local.
# Prefer .env.local values when both exist.
_ = load_dotenv(dotenv_path=".env")
_ = load_dotenv(dotenv_path=".env.local", override=True)
# Also try repository root fallbacks when running from ingestion/ working dir
_ = load_dotenv(dotenv_path="../.env")
_ = load_dotenv(dotenv_path="../.env.local", override=True)

PATH_TO_DBS = os.getenv("ANALYSIS_DB_DIR", ".")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()  # Output to console/terminal
    ],
)

app = FastAPI(
    title="Analysis Agent API",
    description="Ingestion API with background jobs for repo analysis",
    version="1.0.0",
)

# CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "OPTIONS",
        "DELETE",
    ],  # Include DELETE for cleanup endpoints
    allow_headers=["*"],
)


@app.post("/ingest/github", response_model=EnqueueResponse)
async def ingest_github(payload: IngestRequest) -> EnqueueResponse:
    """Enqueue an ingestion job for a public GitHub repository.

    Returns a job_id that can be polled for status.
    """
    job_id = await submit_job(run_ingest_job, payload)
    return EnqueueResponse(job_id=job_id)


@app.get("/ingest/jobs/{job_id}", response_model=JobStatusResponse)
async def get_ingest_job(job_id: str) -> JobStatusResponse:
    rec = get_job(job_id)
    if not rec:
        # if jobid not found, return "done" with no error
        return JobStatusResponse(
            job_id=job_id,
            status=JobStatus.succeeded,
            progress=JobProgress.completed,
            mode=None,
            commit=None,
            counters=None,
            warnings=None,
            error=None,
            created_at="",
            started_at=None,
            finished_at=None,
        )

    result = rec.result
    return JobStatusResponse(
        job_id=rec.id,
        status=rec.status,
        progress=rec.progress,
        mode=result.mode if result else None,
        commit=result.commit if result else None,
        counters=(result.counters if result else None),
        warnings=(result.warnings if result else None),
        error=rec.error,
        created_at=rec.created_at.isoformat(),
        started_at=rec.started_at.isoformat() if rec.started_at else None,
        finished_at=rec.finished_at.isoformat() if rec.finished_at else None,
    )


@app.post("/search", response_model=SemanticSearchResponse)
async def semantic_search(payload: SemanticSearchRequest) -> SemanticSearchResponse:
    # Initialize DB manager
    db_path = f"{PATH_TO_DBS}/{payload.repo_slug}.db"
    # Debug: trace repo and DB path resolution
    print(
        f"[ingestion] /search repo_slug={payload.repo_slug} PATH_TO_DBS={PATH_TO_DBS} db_path={db_path}"
    )
    db = DatabaseManager(db_path=db_path)

    # Configure embedder if needed
    embedder = None
    if payload.mode in ("semantic", "hybrid"):
        api_key = os.getenv("EMBEDDINGS_API_KEY")
        if not api_key:
            if payload.mode == "semantic":
                raise HTTPException(
                    status_code=400,
                    detail="EMBEDDINGS_API_KEY required for semantic mode",
                )
        else:
            embedder = EmbeddingsClient(api_key=api_key)

    processor = SemanticSearchProcessor(db=db, embedder=embedder)

    # Execute search based on mode
    if payload.mode == "semantic":
        entity_type = None
        if payload.entity_types and len(payload.entity_types) == 1:
            entity_type = payload.entity_types[0]
        rows = processor.vector_search(
            payload.query, top_k=payload.top_k, entity_type=entity_type
        )
    elif payload.mode == "symbol":
        rows = processor.fts_definitions(payload.query, top_k=payload.top_k)
    elif payload.mode == "path":
        rows = processor.fts_files(payload.query, top_k=payload.top_k)
    else:
        # hybrid search is WIP (similarity scoring not fully tested)
        rows = processor.hybrid_search(payload.query, top_k=payload.top_k)

    # Shape response
    results: list[SemanticSearchResult] = []
    similarities: list[float] = []

    def to_similarity(distance: float | None) -> float:
        if distance is None:
            return 0.0
        # Convert distance (lower is better) to similarity in [0,1]
        try:
            return 1.0 / (1.0 + float(distance))
        except Exception:
            return 0.0

    for r in rows:
        # Validate required identifiers
        if r.get("entity_type") is None or r.get("entity_id") is None:
            raise HTTPException(
                status_code=500,
                detail="Search result missing required fields: entity_type and/or entity_id",
            )
        entity_type = r.get("entity_type")
        if entity_type not in ("file", "definition"):
            raise HTTPException(
                status_code=500, detail=f"Invalid entity_type: {entity_type}"
            )
        try:
            entity_id = int(cast(str, r.get("entity_id")))
        except Exception:
            raise HTTPException(
                status_code=500, detail="Invalid entity_id in search result"
            )
        entity_name = r.get("entity_name") or r.get("file_path") or ""
        file_path = r.get("file_path") or ""
        language = r.get("language")
        definition_type = r.get("definition_type")
        created_at = r.get("created_at")
        if isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
            except Exception:
                created_at = datetime.utcnow()
        elif created_at is None:
            created_at = datetime.utcnow()

        similarity = to_similarity(r.get("distance"))
        similarities.append(similarity)

        metadata = EmbeddingMetadata(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            file_path=file_path,
            language=language,
            definition_type=definition_type,
            created_at=created_at,
        )

        summary_text = r.get("ai_summary") or ""

        results.append(
            SemanticSearchResult(
                entity_type=entity_type,
                entity_id=entity_id,
                similarity_score=similarity,
                summary_text=summary_text,
                metadata=metadata,
            )
        )

    total = len(results)
    if similarities:
        max_sim = max(similarities)
        min_sim = min(similarities)
    else:
        max_sim = 0.0
        min_sim = 0.0

    return SemanticSearchResponse(
        query=payload.query,
        total_results=total,
        results=results,
        max_similarity=max_sim,
        min_similarity=min_sim,
    )


@app.get("/schema")
def get_openapi_schema():
    """Get OpenAPI schema for TypeScript type generation."""
    return app.openapi()


@app.post("/repo/delete", response_model=DeleteRepoResponse)
async def delete_repo(payload: DeleteRepoRequest) -> DeleteRepoResponse:
    """Delete the local database file and clone directory for a given repo slug.

    Operates within the directory defined by `ANALYSIS_DB_DIR`.
    """
    import re
    import shutil
    from pathlib import Path

    slug = payload.repo_slug.strip()
    if not re.fullmatch(r"[A-Za-z0-9._-]+", slug):
        raise HTTPException(status_code=400, detail="Invalid repo_slug format")

    base_dir = Path(PATH_TO_DBS).resolve()
    db_path = (base_dir / f"{slug}.db").resolve()
    clone_dir = (base_dir / "clones" / slug).resolve()

    # Ensure paths are within base_dir
    try:
        if base_dir not in db_path.parents and db_path != base_dir:
            raise ValueError("db_path escapes base directory")
        if base_dir not in clone_dir.parents and clone_dir != base_dir:
            raise ValueError("clone_dir escapes base directory")
    except Exception:
        raise HTTPException(
            status_code=400, detail="Invalid paths computed for repo_slug"
        )

    db_deleted = False
    clone_deleted = False
    issues: list[str] = []

    # Delete DB file if present
    try:
        if db_path.is_file():
            db_path.unlink()
            db_deleted = True
    except Exception as e:
        logging.exception("Failed to delete DB file")
        issues.append(f"db: {e}")

    # Delete clone directory if present
    try:
        if clone_dir.exists() and clone_dir.is_dir():
            shutil.rmtree(clone_dir)
            clone_deleted = True
    except Exception as e:
        logging.exception("Failed to delete clone directory")
        issues.append(f"clone: {e}")

    msg = None
    if issues:
        msg = "; ".join(issues)

    return DeleteRepoResponse(
        repo_slug=slug, db_deleted=db_deleted, clone_deleted=clone_deleted, message=msg
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
