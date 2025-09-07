"""
Language parser manager for tree-sitter parsers.
Migrated from TypeScript languageParser.ts

This module handles loading and managing tree-sitter parsers and queries
for different programming languages. It adapts from the WASM-based approach
in TypeScript to Python's native tree-sitter bindings.
"""

from pathlib import Path
from typing import cast
from tree_sitter import Language, Parser, Query

from .queries import get_query
from .utils.language_helpers import get_language_name
from tree_sitter_language_pack import SupportedLanguage, get_language


class LanguageParserInfo:
    """Container for language parser and associated queries."""

    def __init__(
        self,
        parser: Parser,
        query: Query,
    ):
        self.parser = parser
        self.query = query


class LanguageParserManager:
    """
    Manages tree-sitter parsers and queries for different programming languages.

    This class handles:
    - Loading language parsers from shared libraries
    - Compiling queries for each language
    - Managing parser instances for different file types
    """

    def __init__(self, language_library_path: str | None = None):
        """
        Initialize the language parser manager.

        Args:
            language_library_path: Path to tree-sitter language libraries directory.
                                  If None, will try to find in common locations.
        """
        self.parsers: dict[str, LanguageParserInfo] = {}

    def _load_language(self, language_name: str) -> Language:
        """
        Load a tree-sitter language.

        Args:
            language_name: Name of the language (e.g., 'javascript', 'typescript')

        Returns:
            Loaded Language object

        Raises:
            ImportError: If language cannot be loaded
        """
        language = get_language(cast(SupportedLanguage, language_name))

        if not language:
            raise LookupError(f"Language {language_name} not available")

        return language

    def _compile_queries(self, language: Language, language_name: str) -> Query:
        """
        Compile queries for a language.

        Args:
            language: Tree-sitter Language object
            language_name: Name of the language

        Returns:
            Tuple of (definitions_query, calls_query, type_query)
        """
        # Map language names to query language names
        query_language_map = {
            "javascript": "javascript",
            "typescript": "typescript",
            "tsx": "tsx",
            "python": "python",
            "rust": "rust",
            "go": "go",
            "c": "c",
            "cpp": "cpp",
            "java": "java",
        }

        # For JSX, use JavaScript queries with JSX calls
        if language_name == "jsx":
            query_language_name = "jsx"
        else:
            query_language_name = query_language_map.get(language_name, language_name)

            # Get definition query
        definitions_query_str = get_query(query_language_name, "definitions")
        if not definitions_query_str:
            raise ValueError(f"No definitions query available for {language_name}")

        definitions_query = Query(language, definitions_query_str)

        return definitions_query

    def load_parser_for_extension(self, extension: str) -> LanguageParserInfo:
        """
        Load a parser for a specific file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            LanguageParserInfo object

        Raises:
            ValueError: If extension is not supported
        """
        # Normalize extension
        if not extension.startswith("."):
            extension = f".{extension}"

            # Check if already loaded
        if extension in self.parsers:
            return self.parsers[extension]

            # Get language name
        language_name = get_language_name(extension)

        print(f"Loading parser for {language_name} ({extension})")

        # Special handling for TSX
        if extension == ".tsx":
            language_name = "tsx"
        elif extension == ".jsx":
            language_name = "javascript"  # JSX uses JavaScript parser

            # Load language
        language = self._load_language(language_name)

        # Create parser
        parser = Parser()
        parser.language = language

        # Compile queries
        query_language = (
            "jsx"
            if extension == ".jsx"
            else "tsx"
            if extension == ".tsx"
            else language_name
        )
        definitions_query = self._compile_queries(language, query_language)

        # Create parser info
        parser_info = LanguageParserInfo(parser, query=definitions_query)
        self.parsers[extension] = parser_info

        return parser_info

    def load_required_parsers(
        self, files_to_parse: list[str]
    ) -> dict[str, LanguageParserInfo]:
        """
        Load parsers for all required file extensions.

        This method analyzes the input files, extracts unique extensions,
        and loads only the necessary parsers for optimal performance.

        Args:
            files_to_parse: List of file paths to be parsed

        Returns:
            Dictionary mapping extensions to LanguageParserInfo objects
        """
        # Extract unique extensions
        extensions_to_load: set[str] = set()
        for file_path in files_to_parse:
            ext = Path(file_path).suffix.lower()
            extensions_to_load.add(ext)

            # Load parsers for each extension
        loaded_parsers: dict[str, LanguageParserInfo] = {}
        for ext in extensions_to_load:
            try:
                parser_info = self.load_parser_for_extension(ext)
                loaded_parsers[ext] = parser_info
            except Exception as e:
                print(f"Warning: Could not load parser for {ext}: {e}")
                continue

        return loaded_parsers

        # Global instance for convenience


_global_parser_manager: LanguageParserManager | None = None


def get_parser_manager() -> LanguageParserManager:
    """Get the global parser manager instance."""
    global _global_parser_manager
    if _global_parser_manager is None:
        _global_parser_manager = LanguageParserManager()
    return _global_parser_manager


def load_required_language_parsers(
    files_to_parse: list[str],
) -> dict[str, LanguageParserInfo]:
    """
    Load required language parsers for a list of files.

    This is a convenience function that uses the global parser manager.

    Args:
        files_to_parse: List of file paths

    Returns:
        Dictionary mapping extensions to LanguageParserInfo objects
    """
    return get_parser_manager().load_required_parsers(files_to_parse)
