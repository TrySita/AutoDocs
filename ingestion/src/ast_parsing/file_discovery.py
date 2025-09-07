"""
File discovery system for AST parsing.
Migrated from TypeScript list-files.ts

This module provides intelligent file discovery with breadth-first traversal
and proper handling of ignore patterns and gitignore files.
"""

import os
import asyncio
import fnmatch
from typing import Set, Optional

from .constants import DEFAULT_IGNORE_PATTERNS
from .utils.path_utils import are_paths_equal, resolve_path


class FileDiscovery:
    """
    Intelligent file discovery system with breadth-first traversal.

    This class handles:
    - Breadth-first directory traversal to avoid infinite loops
    - Gitignore pattern support
    - Default ignore patterns for common build/dependency directories
    - Timeout mechanism for infinite loop protection
    - Special path character handling (NextJS conventions)
    """

    def __init__(self, timeout_seconds: int = 10):
        """
        Initialize the file discovery system.

        Args:
            timeout_seconds: Timeout for directory traversal to prevent infinite loops
        """
        self.timeout_seconds = timeout_seconds
        self.default_ignore_patterns = DEFAULT_IGNORE_PATTERNS.copy()

    def _is_restricted_path(self, absolute_path: str) -> bool:
        """
        Check if a path is restricted (root or home directory).

        Args:
            absolute_path: Absolute path to check

        Returns:
            True if path is restricted, False otherwise
        """
        # Check for root directory
        root = "/"

        if are_paths_equal(absolute_path, root):
            return True

            # Check for home directory
        home_dir = os.path.expanduser("~")
        if are_paths_equal(absolute_path, home_dir):
            return True

        return False

    def _is_targeting_hidden_directory(self, absolute_path: str) -> bool:
        """
        Check if we're targeting a hidden directory (starts with .).

        Args:
            absolute_path: Absolute path to check

        Returns:
            True if targeting hidden directory, False otherwise
        """
        dir_name = os.path.basename(absolute_path)
        return dir_name.startswith(".")

    def _build_ignore_patterns(self, absolute_path: str) -> list[str]:
        """
        Build ignore patterns for directory traversal.

        Args:
            absolute_path: Absolute path being traversed

        Returns:
            List of ignore patterns
        """
        is_target_hidden = self._is_targeting_hidden_directory(absolute_path)

        patterns = self.default_ignore_patterns.copy()

        # Only ignore hidden directories if we're not explicitly targeting a hidden directory
        if not is_target_hidden:
            patterns.append(".*")

        return patterns

    def _load_gitignore_patterns(self, directory: str) -> list[str]:
        """
        Load patterns from .gitignore file if it exists.

        Args:
            directory: Directory to check for .gitignore

        Returns:
            List of gitignore patterns
        """
        gitignore_path = os.path.join(directory, ".gitignore")
        patterns = []

        if os.path.isfile(gitignore_path):
            try:
                with open(gitignore_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            patterns.append(line)
            except (IOError, UnicodeDecodeError):
                # Ignore errors reading .gitignore
                print(f"Warning: Could not read .gitignore at {gitignore_path}")
                pass

        return patterns

    def _is_ignored(
        self,
        file_path: str,
        base_path: str,
        ignore_patterns: list[str],
        gitignore_patterns: list[str],
    ) -> bool:
        """
        Check if a file should be ignored based on patterns.

        Args:
            file_path: Absolute file path
            base_path: Base directory path
            ignore_patterns: List of ignore patterns
            gitignore_patterns: List of gitignore patterns

        Returns:
            True if file should be ignored, False otherwise
        """
        try:
            relative_path = os.path.relpath(file_path, base_path)
        except ValueError:
            # Can happen on Windows with different drives
            return False

            # Convert to forward slashes for pattern matching
        relative_path = relative_path.replace(os.sep, "/")

        # Check default ignore patterns
        for pattern in ignore_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
                # Also check individual path components
            path_parts = relative_path.split("/")
            for part in path_parts:
                if fnmatch.fnmatch(part, pattern.replace("**/", "")):
                    return True

                    # Check gitignore patterns
        for pattern in gitignore_patterns:
            if fnmatch.fnmatch(relative_path, pattern):
                return True
            if fnmatch.fnmatch(os.path.basename(relative_path), pattern):
                return True

        return False

    async def _discover_files_level_by_level(
        self, directory: str, ignore_patterns: list[str], gitignore_patterns: list[str]
    ) -> list[str]:
        """
        Discover files using breadth-first traversal level by level.

        Args:
            directory: Directory to traverse
            ignore_patterns: List of ignore patterns
            gitignore_patterns: List of gitignore patterns

        Returns:
            List of discovered file paths
        """
        results: Set[str] = set()
        queue: list[str] = [directory]
        processed_dirs: Set[str] = set()

        async def process_queue():
            while queue:
                current_dir = queue.pop(0)

                # Avoid processing the same directory multiple times (handles symlinks)
                real_path = os.path.realpath(current_dir)
                if real_path in processed_dirs:
                    continue
                processed_dirs.add(real_path)

                try:
                    # List directory contents
                    entries = await asyncio.get_event_loop().run_in_executor(
                        None, os.listdir, current_dir
                    )

                    for entry in entries:
                        entry_path = os.path.join(current_dir, entry)

                        # Skip if ignored
                        if self._is_ignored(
                            entry_path, directory, ignore_patterns, gitignore_patterns
                        ):
                            continue

                        if os.path.isfile(entry_path):
                            results.add(entry_path)
                        elif os.path.isdir(entry_path):
                            # Add directory to queue for next level
                            queue.append(entry_path)
                            # Also add the directory itself to results if needed
                            results.add(entry_path + "/")

                except (OSError, PermissionError):
                    # Skip directories we can't read
                    continue

            return list(results)

        try:
            # Race between processing and timeout
            return await asyncio.wait_for(process_queue(), timeout=self.timeout_seconds)
        except asyncio.TimeoutError:
            print(
                f"Warning: File discovery timed out after {self.timeout_seconds} seconds, returning partial results"
            )
            return list(results)

    async def list_files(self, dir_path: str, recursive: bool = True) -> list[str]:
        """
        List files in a directory with intelligent filtering.

        Args:
            dir_path: Directory path to list files from
            recursive: Whether to recursively traverse subdirectories

        Returns:
            List of file paths
        """
        absolute_path = resolve_path(dir_path)

        # Check for restricted paths
        if self._is_restricted_path(absolute_path):
            return []

        if not os.path.isdir(absolute_path):
            return []

            # Build ignore patterns
        ignore_patterns = (
            self._build_ignore_patterns(absolute_path) if recursive else []
        )

        # Load gitignore patterns
        gitignore_patterns = (
            self._load_gitignore_patterns(absolute_path) if recursive else []
        )

        if recursive:
            # Use breadth-first traversal
            return await self._discover_files_level_by_level(
                absolute_path, ignore_patterns, gitignore_patterns
            )
        else:
            # Just list files in the current directory
            try:
                entries = await asyncio.get_event_loop().run_in_executor(
                    None, os.listdir, absolute_path
                )
                results = []

                for entry in entries:
                    entry_path = os.path.join(absolute_path, entry)
                    if os.path.isfile(entry_path):
                        results.append(entry_path)

                return results
            except (OSError, PermissionError):
                return []


_global_file_discovery: Optional[FileDiscovery] = None


def get_file_discovery() -> FileDiscovery:
    """Get the global file discovery instance."""
    global _global_file_discovery
    if _global_file_discovery is None:
        _global_file_discovery = FileDiscovery()
    return _global_file_discovery


async def list_files(dir_path: str, recursive: bool = True) -> list[str]:
    """
    Convenience function to list files using the global file discovery instance.

    Args:
        dir_path: Directory path to list files from
        recursive: Whether to recursively traverse subdirectories

    Returns:
        List of file paths
    """
    return await get_file_discovery().list_files(dir_path, recursive)
