"""
Data models for AST parsing, migrated from TypeScript interfaces.
These are plain in-memory containers for parse results; database persistence
is handled separately by the SQLAlchemy models in ``database.models``.
"""

from typing import Any
from datetime import datetime, timezone

from database.models import DefinitionModel

class FileParseResult:
    """Data class equivalent to TypeScript FileParseResult"""

    def __init__(
        self,
        language: str,
        definitions: list[DefinitionModel] | None = None,
    ):
        self.language = language
        self.definitions = definitions or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "definitions": [str(d.__dict__) for d in self.definitions],
        }


class UnpersistedParseResult:
    """
    Container for basic parse results before database persistence.
    Used for hash-based comparison in incremental parsing.
    Function calls and type references are processed separately for changed definitions only.
    """

    def __init__(
        self,
        definitions: list[DefinitionModel],
    ):
        self.definitions = definitions


class ParsedASTResult:
    """Data class equivalent to TypeScript ParsedASTResult"""

    def __init__(
        self,
        directory_path: str,
        total_files: int,
        parsed_files: int,
        unparsed_files: int,
        dependencies: dict[str, Any] | None = None,
        files: dict[str, FileParseResult] | None = None,
        unparsed_files_list: list[str] | None = None,
    ):
        self.metadata = {
            "directoryPath": directory_path,
            "generatedOn": datetime.now(timezone.utc).isoformat(),
            "totalFiles": total_files,
            "parsedFiles": parsed_files,
            "unparsedFiles": unparsed_files,
        }
        self.dependencies = dependencies or {"imports": [], "exports": []}
        self.files = files or {}
        self.unparsed_files = unparsed_files_list or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata,
            "dependencies": self.dependencies,
            "files": {path: result.to_dict() for path, result in self.files.items()},
            "unparsedFiles": self.unparsed_files,
        }
