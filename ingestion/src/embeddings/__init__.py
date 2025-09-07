"""Vector embeddings package for semantic code search.

This package provides functionality to create, store, and query vector embeddings
of code summaries using OpenAI embeddings and SQLite vector storage.
"""

from .generator import EmbeddingsGenerator
from .search import SemanticSearchProcessor
from .models import EmbeddingMetadata

__all__ = [
    "EmbeddingsGenerator",
    "EmbeddingMetadata",
    "SemanticSearchProcessor",
]
