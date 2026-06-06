"""Pydantic models for API request/response payloads.

These are used by FastAPI endpoints and background jobs.
"""

from __future__ import annotations
from typing import Literal
from enum import Enum

from pydantic import BaseModel, Field

from embeddings.models import EmbeddingMetadata


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class JobProgress(str, Enum):
    queued = "queued"
    starting = "starting"
    cloning_repo = "cloning_repo"
    parse = "parse"
    summaries = "summaries"
    embeddings = "embeddings"
    finalize = "finalize"
    completed = "completed"
    failed = "failed"


class IngestRequest(BaseModel):
    """Request payload for POST /ingest/github.

    - github_url: Public GitHub repo URL (https)
    - repo_slug: slug used to name resources
    - force_full: if true, run full ingestion even if DB exists

    Unknown keys (e.g. a legacy ``branch`` or ``db_path``) are ignored: branch
    selection is not implemented, so accepting and silently dropping the field
    avoids breaking clients that still send it.
    """

    github_url: str
    repo_slug: str
    force_full: bool = False


class EnqueueResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: "JobStatus"
    progress: "JobProgress"
    mode: str | None = None
    commit: str | None = None
    counters: dict[str, int] | None = None
    warnings: list[str] | None = None
    error: str | None = None
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class SemanticSearchResult(BaseModel):
    """Individual search result with similarity score.

    `similarity_score` is the vector-distance-derived similarity in [0, 1]. It is
    `None` when the result has no comparable vector distance (e.g. a hybrid
    result matched only by full-text search), so callers are not handed a
    fabricated 0.0 for a result that may in fact rank highly.
    """

    entity_type: Literal["file", "definition"]
    entity_id: int
    similarity_score: float | None
    summary_text: str
    metadata: EmbeddingMetadata


class SemanticSearchResponse(BaseModel):
    """Response model for semantic search results."""

    query: str
    total_results: int
    results: list[SemanticSearchResult]
    max_similarity: float
    min_similarity: float


class SemanticSearchRequest(BaseModel):
    """Request payload for semantic/FTS search."""

    repo_slug: str
    query: str
    mode: Literal["semantic", "symbol", "path", "hybrid"] = "hybrid"
    top_k: int = Field(default=10, ge=1, le=200)
    entity_types: list[Literal["file", "definition"]] | None = None
 

class DeleteRepoRequest(BaseModel):
    """Request payload to delete local data for a repo slug."""

    repo_slug: str


class DeleteRepoResponse(BaseModel):
    """Result of delete operation for a repo slug."""

    repo_slug: str
    db_deleted: bool
    clone_deleted: bool
    message: str | None = None
