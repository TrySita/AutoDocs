"""
Tree-sitter query definitions for AST parsing.
Centralized exports for all query modules.
"""

from .python import PYTHON_QUERY
from .javascript import JAVASCRIPT_QUERY
from .typescript import TYPESCRIPT_QUERY

# Query mapping by language and type
QUERIES = {
    "javascript": {
        "definitions": JAVASCRIPT_QUERY,
    },
    "typescript": {
        "definitions": TYPESCRIPT_QUERY,
    },
    "jsx": {
        "definitions": JAVASCRIPT_QUERY,  # JSX uses JavaScript definitions
    },
    "tsx": {
        "definitions": TYPESCRIPT_QUERY,  # TSX uses TypeScript definitions
    },
    "python": {
        "definitions": PYTHON_QUERY,
    },
}


def get_query(language: str, query_type: str) -> str:
    """
    Get a tree-sitter query for a specific language and type.

    Args:
        language: Language name (javascript, typescript, jsx, tsx)
        query_type: Type of query (definitions, calls, types)

    Returns:
        Query string or empty string if not found
    """
    return QUERIES.get(language, {}).get(query_type, "")


def get_supported_languages() -> list[str]:
    """Get list of supported languages for queries."""
    return list(QUERIES.keys())


def get_query_types_for_language(language: str) -> list[str]:
    """Get available query types for a language."""
    return list(QUERIES.get(language, {}).keys())
