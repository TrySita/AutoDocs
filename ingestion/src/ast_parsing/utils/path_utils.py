"""
Path manipulation utilities for AST parsing.
Migrated from TypeScript path.ts

This module provides cross-platform path handling utilities that ensure
consistent path presentation while maintaining compatibility with the
underlying file system operations.
"""

import os
import platform
from pathlib import Path
from typing import Dict, Optional


def are_paths_equal(path1: Optional[str], path2: Optional[str]) -> bool:
    """
    Safe path comparison that works across different platforms.

    Args:
        path1: First path to compare
        path2: Second path to compare

    Returns:
        True if paths are equal, False otherwise
    """
    if not path1 and not path2:
        return True
    if not path1 or not path2:
        return False

    path1 = normalize_path(path1)
    path2 = normalize_path(path2)

    if platform.system().lower() == "windows":
        return path1.lower() == path2.lower()
    return path1 == path2


def normalize_path(path_str: str) -> str:
    """
    Normalize a path by resolving ./../ segments, removing duplicate slashes,
    and standardizing path separators.

    Args:
        path_str: Path to normalize

    Returns:
        Normalized path
    """
    # Normalize resolves ./.. segments, removes duplicate slashes, and standardizes separators
    normalized = os.path.normpath(path_str)

    # Remove trailing slash, except for root paths
    if len(normalized) > 1 and normalized.endswith(("/", "\\")):
        normalized = normalized[:-1]

    return normalized


def get_cwd(default_cwd: str = "") -> str:
    """
    Returns the current working directory.

    Args:
        default_cwd: Default directory if cwd cannot be determined

    Returns:
        Current working directory path
    """
    try:
        return os.getcwd()
    except OSError:
        return default_cwd


def is_located_in_path(dir_path: str, path_to_check: str) -> bool:
    """
    Returns True if `path_to_check` is located inside `dir_path`.

    Args:
        dir_path: Directory path to check against
        path_to_check: Path to check

    Returns:
        True if path_to_check is inside dir_path, False otherwise
    """
    if not dir_path or not path_to_check:
        return False

    # Handle Extended-Length Paths in Windows
    if dir_path.startswith("\\\\?\\") or path_to_check.startswith("\\\\?\\"):
        return path_to_check.startswith(dir_path)

    try:
        dir_path_resolved = os.path.abspath(dir_path)
        path_to_check_resolved = os.path.abspath(path_to_check)

        relative_path = os.path.relpath(path_to_check_resolved, dir_path_resolved)

        if relative_path.startswith(".."):
            return False

        if os.path.isabs(relative_path):
            # This can happen on Windows when the two paths are on different drives
            return False

        return True

    except ValueError:
        # This can happen on Windows when paths are on different drives
        return False


def as_relative_path(file_path: str) -> str:
    """
    Convert an absolute path to a relative path from the workspace.

    Args:
        file_path: File path to convert

    Returns:
        Relative path if within workspace, otherwise absolute path
    """
    workspace_path = get_cwd()
    if is_located_in_path(workspace_path, file_path):
        return os.path.relpath(file_path, workspace_path)
    return file_path


def resolve_path(path_str: str, base_path_str: Optional[str] = None) -> str:
    """
    Resolve a path to an absolute path.

    Args:
        path_str: Path to resolve
        base_path: Base path for relative resolution (defaults to cwd)

    Returns:
        Absolute path
    """
    if base_path_str is None:
        base_path = Path(get_cwd())
    else:
        base_path = Path(base_path_str)

    print(f"Resolving path: {path_str} with base: {base_path}")

    path = Path(path_str)

    resolved_path = (base_path / path).resolve().as_posix()
    print(f"Resolved path: {resolved_path}")

    return resolved_path


import_path_cache: Dict[str, str] = {}


def get_repo_path(file_path: str, repo_path: str) -> str:
    """
    Get the relative path of a file within a repository.

    Args:
        file_path: Absolute file path
        repo_path: Absolute repository path

    Returns:
        Relative path of the file within the repository
    """
    return os.path.relpath(file_path, repo_path)


def get_file_extension(file_path: str) -> str:
    """
    Get the file extension from a path.

    Args:
        file_path: Path to get extension from

    Returns:
        File extension including the dot (e.g., '.py')
    """
    return Path(file_path).suffix.lower()
