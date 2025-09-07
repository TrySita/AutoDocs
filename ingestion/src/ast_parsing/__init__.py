"""
AST parsing module for extracting code structure and dependencies.

This package provides comprehensive AST parsing capabilities for multiple programming languages
using tree-sitter parsers. It extracts definitions, function calls, imports/exports, and
type information from source code files.

Main Functions:
- parse_file(): Parse a single file
- recursive_parse_directory(): Parse all files in a directory recursively
- main(): CLI entry point

Example Usage:
    >>> from analysis_agent.ast_parsing import parse_file, recursive_parse_directory
    >>>
    >>> # Parse a single file
    >>> result = await parse_file('src/example.ts')
    >>> print(f"Found {len(result.definitions)} definitions")
    >>>
    >>> # Parse entire directory
    >>> result = await recursive_parse_directory('src/')
    >>> print(f"Parsed {result.metadata['parsedFiles']} files")

CLI Usage:
    python -m analysis_agent.ast_parsing /path/to/project output.json
    python -m analysis_agent.ast_parsing --file single_file.ts output.json
"""

# Core parsing functions
from .parser import parse_file, parse_and_persist_repo, get_parser, ASTParser

# Type definitions
from .types import (
    FileParseResult,
    ParsedASTResult,
)

# Utility functions
from .utils.language_helpers import (
    get_language_name,
)


from .file_discovery import list_files

# Constants
from .constants import (
    EXTENSIONS,
    LANGUAGE_NAMES,
    JSX_EXTENSIONS,
    TYPESCRIPT_EXTENSIONS,
    JAVASCRIPT_EXTENSIONS,
    DEFAULT_IGNORE_PATTERNS,
    PACKAGE_FILES,
)

from . import scip_pb2 as scip_pb2

# Version info
__version__ = "1.0.0"
__author__ = "Analysis Agent Team"
__license__ = "MIT"

# All exports
__all__ = [
    "parse_file",
    "parse_and_persist_repo",
    "get_parser",
    "ASTParser",
    "FileParseResult",
    "ParsedASTResult",
    "get_language_name",
    "list_files",
    "EXTENSIONS",
    "LANGUAGE_NAMES",
    "JSX_EXTENSIONS",
    "TYPESCRIPT_EXTENSIONS",
    "JAVASCRIPT_EXTENSIONS",
    "DEFAULT_IGNORE_PATTERNS",
    "PACKAGE_FILES",
]
