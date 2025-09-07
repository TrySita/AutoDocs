"""
Language helper utilities for AST parsing.
Migrated from TypeScript languageHelpers.ts
"""

from ..constants import LANGUAGE_NAMES

def get_language_name(ext: str) -> str:
    """
    Helper function to get language name from extension.

    Args:
        ext: File extension (with or without leading dot)

    Returns:
        Language name for tree-sitter parser
    """
    # Ensure extension starts with dot
    if not ext.startswith("."):
        ext = f".{ext}"

    return LANGUAGE_NAMES.get(ext, ext.lstrip("."))
