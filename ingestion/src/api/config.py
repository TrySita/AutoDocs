"""Validated application configuration loaded once at startup.

This is the single place that reads environment variables for the API. Every
other module imports the parsed `AppConfig` (via `load_config`) instead of
calling `os.getenv` directly, so misconfiguration fails loudly at boot rather
than mid-request or mid-job.

`EMBEDDINGS_API_KEY` is required by every endpoint that can run a semantic
search or an ingestion job, so it is validated at startup. CORS origins are
validated here too: production must declare its allowed origins explicitly
(never a wildcard with credentials), and development falls back to a sensible
localhost default.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_DEV_DEFAULT_ORIGINS: tuple[str, ...] = (
    "http://localhost:3000",
    "http://localhost:8000",
)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or malformed."""


@dataclass(frozen=True)
class AppConfig:
    """Validated configuration for the ingestion API."""

    embeddings_api_key: str
    analysis_db_dir: str
    environment: str
    cors_allowed_origins: list[str]


def _detect_environment() -> str:
    """Return the deployment environment, defaulting to development.

    `ENVIRONMENT` takes precedence, but the Docker stack and the .env templates
    only export `NODE_ENV` (never `ENVIRONMENT`), so fall back to it. Without
    this fallback the API would silently run with the development CORS default
    in production.
    """
    explicit = os.getenv("ENVIRONMENT", "").strip().lower()
    if explicit:
        return explicit
    node_env = os.getenv("NODE_ENV", "").strip().lower()
    if node_env:
        return node_env
    return "development"


def parse_cors_origins(environment: str | None = None) -> list[str]:
    """Parse the allowed CORS origins from the environment.

    Origins are read from `CORS_ALLOWED_ORIGINS` as a comma-separated list. In
    production an explicit list is mandatory: failing to set it raises
    `ConfigError` so we never pair a wildcard origin with credentialed
    requests. In development we fall back to localhost.
    """
    env = (environment or _detect_environment()).strip().lower()
    raw = os.getenv("CORS_ALLOWED_ORIGINS", "").strip()
    origins = [o.strip() for o in raw.split(",") if o.strip()]

    if "*" in origins:
        msg = (
            "CORS_ALLOWED_ORIGINS must not contain '*': a wildcard origin "
            + "cannot be combined with credentialed requests."
        )
        raise ConfigError(msg)

    if origins:
        return origins

    if env == "production":
        msg = (
            "CORS_ALLOWED_ORIGINS is required in production. Set it to a "
            + "comma-separated list of allowed frontend origins."
        )
        raise ConfigError(msg)

    logger.warning(
        "CORS_ALLOWED_ORIGINS not set; defaulting to localhost origins for the '%s' environment.",
        env,
    )
    return list(_DEV_DEFAULT_ORIGINS)


def load_config() -> AppConfig:
    """Parse and validate all required configuration, failing loudly on error."""
    environment = _detect_environment()

    embeddings_api_key = os.getenv("EMBEDDINGS_API_KEY", "").strip()
    if not embeddings_api_key:
        msg = (
            "EMBEDDINGS_API_KEY is required. Set it in the environment before "
            + "starting the API."
        )
        raise ConfigError(msg)

    analysis_db_dir = os.getenv("ANALYSIS_DB_DIR", ".").strip() or "."
    cors_allowed_origins = parse_cors_origins(environment)

    return AppConfig(
        embeddings_api_key=embeddings_api_key,
        analysis_db_dir=analysis_db_dir,
        environment=environment,
        cors_allowed_origins=cors_allowed_origins,
    )
