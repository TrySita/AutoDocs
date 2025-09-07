# type: ignore
"""
Shared test fixtures for AST parsing tests.
"""

import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import sys

from database.manager import DatabaseManager

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from ast_parsing import parse_file


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def db_manager() -> DatabaseManager:
    """Create a database manager instance for the test session."""
    db_manager = DatabaseManager(expire_on_commit=False)  # noqa: F821
    return db_manager


@pytest_asyncio.fixture(scope="session")
async def comprehensive_parse_result(db_manager):
    """Parse the comprehensive test file once for all tests."""
    test_file_path = Path(__file__).parent / "test_files" / "test-comprehensive.tsx"
    return await parse_file(test_file_path.as_posix(), db_manager=db_manager)


@pytest_asyncio.fixture(scope="session")
async def import_export_parse_result(db_manager):
    """Parse the import-export test file once for all tests."""
    test_file_path = Path(__file__).parent / "test_files" / "test-import-export.ts"
    return await parse_file(test_file_path.as_posix(), db_manager=db_manager)


@pytest_asyncio.fixture(scope="session")
async def jsx_parse_result(db_manager):
    """Parse the JSX components test file once for all tests."""
    test_file_path = Path(__file__).parent / "test_files" / "test-jsx-components.tsx"
    return await parse_file(test_file_path.as_posix(), db_manager=db_manager)


@pytest_asyncio.fixture(scope="session")
async def types_parse_result(db_manager):
    """Parse the types test file once for all tests."""
    test_file_path = Path(__file__).parent / "test_files" / "test-types.ts"
    return await parse_file(test_file_path.as_posix(), db_manager=db_manager)

@pytest_asyncio.fixture(scope="session")
async def default_export_test(db_manager):
    """Parse the default export test file once for all tests."""
    test_file_path = Path(__file__).parent / "test_files" / "test-default-export.ts"
    return await parse_file(test_file_path.as_posix(), db_manager=db_manager)
