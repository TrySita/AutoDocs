"""
File system utilities for AST parsing.
Migrated from TypeScript fs.ts
"""

import os
import asyncio
from typing import Union


async def file_exists_at_path(file_path: str) -> bool:
    """
    Helper function to check if a path exists.

    Args:
        file_path: The path to check

    Returns:
        True if the path exists, False otherwise
    """
    try:
        return await asyncio.get_event_loop().run_in_executor(
            None, os.path.exists, file_path
        )
    except Exception:
        return False


# Synchronous versions for compatibility
def file_exists_at_path_sync(file_path: str) -> bool:
    """Synchronous version of file_exists_at_path."""
    return os.path.exists(file_path)
