"""Pydantic models for vector embeddings metadata and responses."""

from datetime import datetime, timezone
from pydantic import BaseModel, Field
from typing import Literal


class EmbeddingMetadata(BaseModel):
    """Metadata for vector embeddings stored with each vector."""

    entity_type: Literal["file", "definition"]
    entity_id: int
    entity_name: str
    file_path: str
    language: str | None = None
    definition_type: str | None = None  # Only for definitions
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))