"""Regression tests for AST parser bugs 4, 7, 10, and 12 (docs/tasks.md Part 1).

* Bug 4  -- JavaScript/JSX definitions are never extracted because
  ``queries/javascript.py`` used generic ``@def``/``@name`` captures while the
  parser searches for typed ``@def_<kind>``/``@name_<kind>`` captures.
* Bug 7  -- Definition dedup keyed on the start line alone, dropping the second
  of two distinct definitions that start on the same line (``a = 1; b = 2``).
* Bug 10 -- ``_handle_file_deletions_and_renames`` opened its own
  ``session_scope`` (which commits) while the surrounding parse uses the
  ambient ``get_current_session()``, so deletions could commit even when the
  enclosing parse later fails.
* Bug 12 -- ``ASTParser.parse_file`` never associated extracted definitions with
  the created ``FileModel`` and stored an absolute ``file_path`` instead of the
  relative path used everywhere else.

None of these tests hit the network or require API keys: tree-sitter parsing is
local and the database is in-memory.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

import pytest

from ast_parsing import parse_file
import ast_parsing.parser as parser_module
from ast_parsing.parser import ASTParser
from database.manager import (
    DatabaseManager,
    session_scope,
    set_session_context,
)
from database.models import FileModel
from ast_parsing.utils.git_utils import GitChanges

TEST_FILES = Path(__file__).parent / "test_ast_parsing" / "test_files"


@pytest.fixture(autouse=True)
def reset_global_parser():
    """Reset the module-level parser singleton around each test.

    ``get_parser`` caches a single ASTParser bound to the first db_manager it
    sees, so without this reset a later test's module-level ``parse_file`` would
    silently write to an earlier test's database. Resetting keeps each test's
    in-memory database independent.
    """
    parser_module._global_parser = None
    yield
    parser_module._global_parser = None


def _make_db() -> DatabaseManager:
    return DatabaseManager(expire_on_commit=False)


# --- Bug 4: typed JavaScript/JSX captures ----------------------------------


@pytest.mark.asyncio
async def test_javascript_definitions_are_extracted() -> None:
    """A plain ``.js`` file must yield typed definitions, not an empty list.

    The expected kinds mirror the TypeScript query's classification exactly
    (bug 4 asks the JS query to mirror ``typescript.py``): a ``const``-bound
    value is a ``constant``, a ``let``-bound value is a ``variable``, a named
    ``function`` declaration is a ``function``, and so on.
    """
    db = _make_db()
    result = await parse_file((TEST_FILES / "test-bugfix-defs.js").as_posix(), db)

    by_name = {d.name: d.definition_type for d in result.definitions}

    # Named function declaration.
    assert by_name.get("greet") == "function"
    # Class declaration and a method on its own line.
    assert by_name.get("Calculator") == "class"
    assert by_name.get("square") == "method"
    # const-bound values are classified as constants (matches the TS query).
    assert by_name.get("add") == "constant"
    assert by_name.get("PI") == "constant"
    assert by_name.get("subtract") == "constant"
    # let-bound value is classified as a variable (matches the TS query).
    assert by_name.get("multiply") == "variable"


@pytest.mark.asyncio
async def test_jsx_definitions_are_extracted() -> None:
    """A ``.jsx`` file routed through the JavaScript parser must yield defs."""
    db = _make_db()
    result = await parse_file((TEST_FILES / "test-bugfix-component.jsx").as_posix(), db)

    by_name = {d.name: d.definition_type for d in result.definitions}
    # Function-declaration component.
    assert by_name.get("Header") == "function"
    # const arrow component (classified as a constant, mirroring the TS query).
    assert by_name.get("Footer") == "constant"
    # Class component and its render method.
    assert by_name.get("Panel") == "class"
    assert by_name.get("render") == "method"


# --- Bug 7: dedup keyed on (start_line, name), not start_line alone ---------


@pytest.mark.asyncio
async def test_two_definitions_on_one_line_are_both_kept(tmp_path: Path) -> None:
    """``const a = () => 1, b = () => 2`` defines two functions on one line."""
    src = "const a = () => 1, b = () => 2;\n"
    js_file = tmp_path / "two_on_one_line.js"
    js_file.write_text(src, encoding="utf-8")

    db = _make_db()
    result = await parse_file(js_file.as_posix(), db)

    names = sorted(d.name for d in result.definitions)
    assert names == ["a", "b"], (
        "both same-line function definitions must be kept; "
        f"got {[d.name for d in result.definitions]}"
    )


# --- Bug 10: single session context for the whole parse --------------------


@pytest.mark.asyncio
async def test_deletion_uses_ambient_session_and_rolls_back_with_it() -> None:
    """A deletion handled mid-parse must roll back if the ambient txn rolls back.

    The bug opened a private ``session_scope`` that commits immediately, so a
    deletion persisted even when the enclosing parse later failed. With a single
    ambient session, rolling that session back must undo the deletion.
    """
    db = _make_db()
    parser = ASTParser(db)

    with session_scope(db) as session:
        file_model = FileModel(
            file_path="pkg/gone.js",
            file_content="x = 1",
            language="javascript",
        )
        session.add(file_model)
        session.commit()

    # Use a raw session we control so we can roll it back ourselves.
    raw_session = db.SessionLocal()
    set_session_context(raw_session)
    try:
        git_changes = GitChanges(
            added=[], modified=[], deleted=["pkg/gone.js"], renamed=[]
        )
        # repo_path="" so get_repo_path returns the path unchanged.
        await parser._handle_file_deletions_and_renames(git_changes, repo_path="")

        # The deletion is pending in the ambient session, not yet committed.
        # Simulate the enclosing parse failing: roll back the ambient session.
        raw_session.rollback()
    finally:
        raw_session.close()
        set_session_context(None)

    # After the rollback the file must still exist: the deletion was part of the
    # ambient transaction, not a separately-committed side transaction.
    with session_scope(db) as session:
        survivors = session.query(FileModel).filter_by(file_path="pkg/gone.js").all()
    assert len(survivors) == 1, (
        "deletion must roll back with the ambient transaction; the file should "
        "still exist after the enclosing parse rolled back"
    )


# --- Bug 12: parse_file associates defs with the file and uses a relative path


@pytest.mark.asyncio
async def test_parse_file_associates_definitions_with_file(tmp_path: Path) -> None:
    """parse_file must attach extracted definitions to the created FileModel."""
    js_file = tmp_path / "single.js"
    js_file.write_text("function only() { return 1; }\n", encoding="utf-8")

    db = _make_db()
    result = await parse_file(js_file.as_posix(), db)

    assert len(result.definitions) >= 1
    for definition in result.definitions:
        assert isinstance(definition.file, FileModel), (
            "each definition must be associated with the created FileModel"
        )


@pytest.mark.asyncio
async def test_parse_file_stores_relative_path() -> None:
    """parse_file must store a workspace-relative path, not the absolute path.

    The parser persists paths relative to the workspace everywhere else; the
    single-file path stored an absolute path, which never matches those
    records. A file located under the current working directory must therefore
    be stored relative to it.
    """
    # Create the file under the current working directory so as_relative_path
    # can produce a relative path (it returns the absolute path for files
    # outside the workspace, which is correct but not what this test asserts).
    work_dir = Path(tempfile.mkdtemp(dir=os.getcwd()))
    try:
        js_file = work_dir / "single.js"
        js_file.write_text("function only() { return 1; }\n", encoding="utf-8")

        db = _make_db()
        await parse_file(js_file.as_posix(), db)

        with session_scope(db) as session:
            files = session.query(FileModel).all()
        assert len(files) == 1
        stored_path = files[0].file_path
        assert not Path(stored_path).is_absolute(), (
            f"file_path must be relative, not absolute; got {stored_path!r}"
        )
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
