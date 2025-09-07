import hashlib
import re

from database.models import DefinitionModel, FileModel, ImportModel
from sqlalchemy.orm import Session


def strip_typescript_comments(source: str) -> str:
    """Remove TypeScript comments from source.

    Handles:
    - // single-line comments
    - /** */ multi-line comments (JSDoc style)
    """
    # Remove JSDoc-style multi-line comments /** ... */
    without_jsdoc = re.sub(r"/\*\*[\s\S]*?\*/", "", source)
    # Remove // single-line comments
    without_single = re.sub(r"//.*", "", without_jsdoc)
    return without_single


def strip_comments(language: str, source_code: str) -> str:
    """Remove comments from source code based on the programming language."""
    if language.lower() == "typescript":
        return strip_typescript_comments(source_code)
    # Add more language-specific comment stripping as needed
    return source_code


def hash_source_code(def_name: str, source_code_cleaned: str) -> str:
    """Compute a stable hash for a definition's source.

    - Removes occurrences of the definition name so renames don't change the hash.
    - Normalizes whitespace/newlines before hashing.
    """

    # Remove the definition name tokens so renames don't affect the hash
    if def_name and def_name != "anonymous":
        source_code_cleaned = re.sub(
            rf"\b{re.escape(def_name)}\b", "", source_code_cleaned
        )

    # Normalize whitespace: trim lines, drop empty lines, normalize newlines
    cleaned = "\n".join(
        ln.strip()
        for ln in source_code_cleaned.replace("\r\n", "\n")
        .replace("\r", "\n")
        .splitlines()
        if ln.strip()
    )

    return hashlib.sha256(cleaned.encode("utf-8")).hexdigest()
