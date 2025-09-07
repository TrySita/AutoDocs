"""Simple in-memory job manager for background ingestion tasks.

This module provides a minimal async job system:
- submit_job: schedules an async coroutine with a payload and returns a job_id
- get_job: fetch job status/result
- update_progress / complete / fail: helpers for workers to report status

Note: This is an in-memory store. For resilience, persist to a DB in the future.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Callable, Awaitable, TypeVar


from api.schemas import JobStatus, JobProgress


@dataclass
class JobResult:
    """Result payload returned by an ingestion job."""

    mode: str | None = None  # "full" | "incremental"
    commit: str | None = None
    counters: dict[str, int] = field(default_factory=dict)
    turso_database_url: str | None = None
    pinecone_index: str | None = None
    pinecone_namespace: str | None = None
    warnings: list[str] = field(default_factory=list)


@dataclass
class JobRecord:
    id: str
    status: JobStatus = JobStatus.queued
    progress: JobProgress = JobProgress.queued
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: JobResult | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        d: dict[str, object] = asdict(self)
        # Convert datetimes to isoformat for JSON response
        d["created_at"] = self.created_at.isoformat()
        if self.started_at:
            d["started_at"] = self.started_at.isoformat()
        if self.finished_at:
            d["finished_at"] = self.finished_at.isoformat()
        return d


_jobs: dict[str, JobRecord] = {}
_lock = asyncio.Lock()

# Set up logger
logger = logging.getLogger(__name__)

# Generic payload type for jobs
P = TypeVar("P")

async def _run_job(
    job_id: str,
    worker: Callable[[str, P], Awaitable[JobResult | None]],
    payload: P,
) -> None:
    """Internal task runner that executes the worker and updates job status."""
    record = _jobs.get(job_id)
    if not record:
        logger.warning(f"Job {job_id} not found in records")
        return

    logger.info(f"Starting job {job_id}")
    record.status = JobStatus.running
    record.started_at = datetime.now(timezone.utc)
    record.progress = JobProgress.starting

    try:
        result = await worker(job_id, payload)
        record.result = result or JobResult()
        record.status = JobStatus.succeeded
        record.progress = JobProgress.completed
        record.finished_at = datetime.now(timezone.utc)
        logger.info(f"Job {job_id} completed successfully")
    except Exception as e:  # noqa: BLE001
        tb = traceback.format_exc()
        record.status = JobStatus.failed
        record.error = f"{e}\n{tb}"
        record.progress = JobProgress.failed
        record.finished_at = datetime.now(timezone.utc)
        logger.error(f"Job {job_id} failed: {e}")


async def submit_job(
    worker: Callable[[str, P], Awaitable[JobResult | None]],
    payload: P,
) -> str:
    """Submit a job and return its job_id."""
    job_id = str(uuid.uuid4())
    async with _lock:
        _jobs[job_id] = JobRecord(id=job_id)

    logger.info(f"Submitted job {job_id}")
    # Schedule the job in the current event loop
    _ = asyncio.create_task(_run_job(job_id, worker, payload))
    return job_id


def get_job(job_id: str) -> JobRecord | None:
    return _jobs.get(job_id)


def update_progress(job_id: str, message: JobProgress) -> None:
    rec = _jobs.get(job_id)
    if rec:
        rec.progress = message
        logger.info(f"Job {job_id} progress: {message}")


def complete(job_id: str, result: JobResult) -> None:
    rec = _jobs.get(job_id)
    if rec:
        rec.result = result
        rec.status = JobStatus.succeeded
        rec.progress = JobProgress.completed
        rec.finished_at = datetime.now(timezone.utc)


def fail(job_id: str, error: str) -> None:
    rec = _jobs.get(job_id)
    if rec:
        rec.status = JobStatus.failed
        rec.error = error
        rec.progress = JobProgress.failed
        rec.finished_at = datetime.now(timezone.utc)
