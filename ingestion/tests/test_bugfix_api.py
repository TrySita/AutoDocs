"""Focused regression tests for API bugs 14, 17, 18, 19.

These tests do not touch the network or require API keys: the job-runner
tests inject a trivial worker, and the config tests exercise pure
environment parsing/validation.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

import pytest
from fastapi.testclient import TestClient

# Add src to Python path (mirrors tests/test_api/conftest.py).
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from api.main import app  # noqa: E402
from api import job_manager  # noqa: E402
from api.job_manager import JobRecord, submit_job  # noqa: E402
from api.schemas import JobStatus  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# --- Bug 14: unknown job IDs must 404, not report success ---


def test_unknown_job_id_returns_404(client: TestClient) -> None:
    """A job ID that is not in the store must be a 404, never 'succeeded'."""
    response = client.get("/ingest/jobs/does-not-exist-1234")
    assert response.status_code == 404, (
        f"expected 404 for unknown job id, got {response.status_code}: "
        f"{response.text}"
    )


# --- Bug 17: failed jobs must not leak tracebacks to API clients ---


def test_failed_job_error_is_sanitized_no_traceback() -> None:
    """A worker raising must store a one-line message, not a full traceback."""

    async def boom(_job_id: str, _payload: object) -> None:
        raise ValueError("/secret/internal/path/leak.py exploded")

    async def run() -> JobRecord:
        job_id = await submit_job(boom, payload=object())
        # Drain the scheduled task.
        for _ in range(50):
            rec = job_manager.get_job(job_id)
            assert rec is not None
            if rec.status in (JobStatus.failed, JobStatus.succeeded):
                return rec
            await asyncio.sleep(0.01)
        raise AssertionError("job did not finish")

    rec = asyncio.run(run())

    assert rec.status == JobStatus.failed
    assert rec.error is not None
    # The leaked traceback signature must be gone.
    assert "Traceback" not in rec.error
    assert "\n" not in rec.error
    assert ".py" not in rec.error
    assert 'File "' not in rec.error


def test_failed_job_response_omits_traceback(client: TestClient) -> None:
    """The HTTP status response for a failed job must not include a traceback."""

    async def boom(_job_id: str, _payload: object) -> None:
        raise RuntimeError("boom at /home/app/secret.py")

    async def run() -> str:
        job_id = await submit_job(boom, payload=object())
        for _ in range(50):
            rec = job_manager.get_job(job_id)
            assert rec is not None
            if rec.status in (JobStatus.failed, JobStatus.succeeded):
                return job_id
            await asyncio.sleep(0.01)
        raise AssertionError("job did not finish")

    job_id = asyncio.run(run())
    response = client.get(f"/ingest/jobs/{job_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert "Traceback" not in (body["error"] or "")
    assert "secret.py" not in (body["error"] or "")


# --- Bug 18: centralized startup config validation ---


def test_config_requires_embeddings_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Loading config without EMBEDDINGS_API_KEY must fail loudly."""
    from api.config import ConfigError, load_config

    monkeypatch.delenv("EMBEDDINGS_API_KEY", raising=False)
    with pytest.raises(ConfigError):
        load_config()


def test_config_returns_validated_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """With required vars present, config parses them into a typed object."""
    from api.config import load_config

    monkeypatch.setenv("EMBEDDINGS_API_KEY", "real-key")
    monkeypatch.setenv("ANALYSIS_DB_DIR", "/tmp/dbs")
    cfg = load_config()
    assert cfg.embeddings_api_key == "real-key"
    assert cfg.analysis_db_dir == "/tmp/dbs"


# --- Bug 19: CORS origins come from env, not wildcard ---


def test_cors_origins_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CORS origins must be parsed from CORS_ALLOWED_ORIGINS, not wildcard."""
    from api.config import parse_cors_origins

    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "https://a.example.com, https://b.example.com"
    )
    origins = parse_cors_origins(environment="production")
    assert origins == ["https://a.example.com", "https://b.example.com"]
    assert "*" not in origins


def test_cors_wildcard_with_credentials_is_rejected_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Production must not silently fall back to wildcard origins."""
    from api.config import ConfigError, parse_cors_origins

    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    with pytest.raises(ConfigError):
        parse_cors_origins(environment="production")


def test_cors_dev_default_is_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """Development defaults to localhost origins, never wildcard."""
    from api.config import parse_cors_origins

    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
    origins = parse_cors_origins(environment="development")
    assert origins
    assert "*" not in origins
    assert all(o.startswith("http://localhost") for o in origins)


def test_node_env_production_is_detected_when_environment_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Docker sets NODE_ENV=production but not ENVIRONMENT; detect production.

    The compose stack and .env templates export NODE_ENV, never ENVIRONMENT.
    If detection keyed only on ENVIRONMENT the API would silently run with the
    development CORS fallback in production.
    """
    from api.config import _detect_environment

    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setenv("NODE_ENV", "production")
    assert _detect_environment() == "production"


def test_environment_takes_precedence_over_node_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An explicit ENVIRONMENT wins over NODE_ENV."""
    from api.config import _detect_environment

    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("NODE_ENV", "production")
    assert _detect_environment() == "development"
