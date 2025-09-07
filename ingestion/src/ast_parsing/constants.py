"""
Constants for AST parsing, migrated from TypeScript.
Contains file extension constants and language mappings.
"""

from typing import List, Dict

# Supported file extensions with leading dots
EXTENSIONS: List[str] = [
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".py",
    # # Rust
    # ".rs",
    # ".go",
    # # C
    # ".c",
    # ".h",
    # # C++
    # ".cpp",
    # ".hpp",
    # # C#
    # ".cs",
    # # Ruby
    # ".rb",
    # ".java",
    # ".php",
    # ".swift",
    # # Kotlin
    # ".kt",
]

# Language names for tree-sitter parsers
LANGUAGE_NAMES: dict[str, str] = {
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".py": "python",
    # ".rs": "rust",
    # ".go": "go",
    # ".c": "c",
    # ".h": "c",
    # ".cpp": "cpp",
    # ".hpp": "cpp",
    # ".cs": "c_sharp",
    # ".rb": "ruby",
    # ".java": "java",
    # ".php": "php",
    # ".swift": "swift",
    # ".kt": "kotlin",
}

KINDS = [
    "function",
    "method",
    "class",
    "interface",
    "type_alias",
    "enum",
    "module",
    "constant",
    "variable",
]

# Extensions that support JSX/TSX syntax
JSX_EXTENSIONS: list[str] = [".jsx", ".tsx"]

# Extensions that support TypeScript
TYPESCRIPT_EXTENSIONS: list[str] = [".ts", ".tsx"]

# Extensions that support JavaScript
JAVASCRIPT_EXTENSIONS: list[str] = [".js", ".jsx"]

# Directories commonly ignored during parsing
DEFAULT_IGNORE_PATTERNS: list[str] = [
    "node_modules",
    ".git",
    ".next",
    ".nuxt",
    "dist",
    "build",
    ".svelte-kit",
    ".vscode",
    ".idea",
    "__pycache__",
    ".pytest_cache",
    "target",  # Rust
    "vendor",  # Go
    ".gradle",  # Java
    ".mvn",  # Maven
]

# Package file names for external dependency detection
PACKAGE_FILES: dict[str, str] = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "poetry",
    "Cargo.toml": "cargo",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "composer.json": "composer",
    "Gemfile": "bundler",
    "Package.swift": "swift",
}
