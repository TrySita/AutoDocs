"""Test configuration for API tests."""

import pytest
from pathlib import Path
import sys
import os

# Add src to Python path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring database"
    )

@pytest.fixture(scope="session")
def test_database_path():
    """Provide the test database path."""
    db_path = Path(__file__).parent.parent.parent / "real-summaries-2.db"
    return db_path

@pytest.fixture(scope="session", autouse=True)
def check_test_environment(test_database_path):
    """Check that the test environment is properly set up."""
    if not test_database_path.exists():
        pytest.skip(
            f"Database file {test_database_path} not found. "
            "Run the analysis pipeline first to generate test data."
        )

@pytest.fixture(autouse=True)
def ensure_working_directory():
    """Ensure tests run from the project root directory."""
    project_root = Path(__file__).parent.parent.parent
    original_cwd = os.getcwd()
    os.chdir(project_root)
    yield
    os.chdir(original_cwd)