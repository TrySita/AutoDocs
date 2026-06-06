"""Regression tests for bug 2 (imports/exports removal) and bug 3 (branch field).

Bug 2: the imports/exports layer was never populated, only wiped. The
`ImportModel`, the `imports` table, and the import/export carrier fields must be
gone, and a single-file parse must still work end to end without an imports
table.

Bug 3: `IngestRequest.branch` was accepted, logged, and ignored. The field is
removed; an incoming payload that still carries ``branch`` (as the web client
does) must be accepted and the key silently dropped.
"""

from pathlib import Path

import pytest
from sqlalchemy import inspect

import database.models as models
from api.schemas import IngestRequest
from ast_parsing import parse_file
from database.manager import DatabaseManager


def test_import_model_is_removed() -> None:
    """ImportModel and the imports table no longer exist."""
    assert not hasattr(models, "ImportModel")
    assert "imports" not in models.Base.metadata.tables


def test_database_package_does_not_reexport_import_model() -> None:
    """The database package must not re-export the removed ImportModel."""
    import database

    assert "ImportModel" not in database.__all__
    assert not hasattr(database, "ImportModel")


@pytest.mark.asyncio
async def test_parse_file_works_without_imports_table() -> None:
    """A single-file parse persists definitions on a schema with no imports table."""
    db = DatabaseManager(db_path=":memory:", echo=False, expire_on_commit=False)

    table_names = inspect(db.engine).get_table_names()
    assert "imports" not in table_names

    fixture = (
        Path(__file__).parent
        / "test_ast_parsing"
        / "test_files"
        / "test-default-export.ts"
    )
    result = await parse_file(fixture.as_posix(), db_manager=db)

    # End-to-end parse still extracts definitions.
    assert any(d.name == "NewFunc" for d in result.definitions)
    # The parse result no longer carries an imports/exports layer.
    assert not hasattr(result, "imports")
    assert not hasattr(result, "exports")


def test_ingest_request_ignores_branch_key() -> None:
    """branch is no longer a field; payloads that still send it are accepted."""
    payload = IngestRequest.model_validate(
        {
            "github_url": "https://github.com/example/repo",
            "repo_slug": "repo",
            "branch": None,
            "db_path": "repo.db",
            "force_full": False,
        }
    )

    assert payload.github_url == "https://github.com/example/repo"
    assert payload.repo_slug == "repo"
    assert not hasattr(payload, "branch")
