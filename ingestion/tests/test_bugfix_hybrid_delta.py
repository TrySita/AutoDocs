"""Regression test for Bug 1 -- the parse delta never reaches the worker.

``run_ingest_job`` (api/ingestion.py) used to read the parse delta from
``get_parser(local_db).current_delta`` -- the module-global singleton ASTParser,
which never runs a parse, so its ``current_delta`` is always ``None``. The real
delta lives on the ``ASTParser`` that ``HybridParser.parse_repository`` builds
internally. As a result incremental mode never triggered.

This test exercises the exact seam the worker must consume: it runs
``HybridParser.parse_repository`` across a full then an incremental (mocked git)
parse and asserts the returned result carries a non-None delta describing the
change -- while the module-global singleton's delta stays ``None`` (proving the
old source was wrong).

It does not hit the network or any SCIP tooling: git info/diff and the SCIP
indexer are mocked, following tests/test_ast_parsing/test_git_incremental_parsing.py
and tests/test_bugfix_scip_mapping.py.
"""

from __future__ import annotations

import os

import pytest

from ast_parsing import hybrid_parser as hybrid_parser_module
from ast_parsing.hybrid_parser import HybridParser
from ast_parsing.parser import get_parser
from ast_parsing.scip_symbol_resolution import ScipResult
from database.manager import DatabaseManager, session_scope
from database.models import RepositoryModel


def _empty_scip_result() -> ScipResult:
    """An empty SCIP result so the hybrid parse needs no SCIP tooling."""
    return ScipResult(
        files={},
        symbol_to_info={},
        symbol_to_references={},
        edges_intra_repo=[],
    )


@pytest.mark.asyncio
async def test_hybrid_parse_repository_exposes_incremental_delta(tmp_path, monkeypatch):
    db = DatabaseManager(expire_on_commit=False)

    # Fresh module-global parser singleton so it is unambiguously untouched.
    import ast_parsing.parser as parser_module

    monkeypatch.setattr(parser_module, "_global_parser", None, raising=False)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    file_a = repo_dir / "file_a.ts"
    file_a_v1 = "function foo() {\n  return 1;\n}\n\nfunction bar() {\n  return 2;\n}\n"
    file_a.write_text(file_a_v1, encoding="utf-8")

    # The parser computes the incremental diff via this function; mock it so the
    # second (commit B) parse runs incrementally with no real git involved.
    from ast_parsing.utils.git_utils import GitChanges

    def fake_compare(
        before_commit_hash: str,
        after_commit_hash: str,
        repo_path: str,
        remote_origin_url: str | None = None,
    ) -> GitChanges:
        return GitChanges(
            added=["file_c.ts"], modified=["file_a.ts"], deleted=[], renamed=[]
        )

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.compare_commits_and_get_changed_files",
        fake_compare,
    )
    monkeypatch.setattr(
        "ast_parsing.parser.compare_commits_and_get_changed_files",
        fake_compare,
    )

    # SCIP indexing is irrelevant to delta propagation -- stub it out entirely.
    monkeypatch.setattr(
        hybrid_parser_module,
        "collect_repo_symbols_with_scip",
        lambda *args, **kwargs: _empty_scip_result(),
    )

    def relp(name: str) -> str:
        return os.path.relpath((repo_dir / name).as_posix(), repo_dir.as_posix())

    parser = HybridParser(db)

    # Full parse first (establishes commit A as the stored repository state).
    with session_scope(db) as session:
        repo = RepositoryModel(
            remote_origin_url="mock://hybrid-delta", repo_slug="hybrid-delta"
        )
        session.add(repo)
        session.flush()
        full_result = await parser.parse_repository(
            session=session,
            repo_path=repo_dir.as_posix(),
            repository=repo,
            new_commit_hash="A",
        )

    # A full (first) parse has no incremental delta.
    assert full_result.delta is None

    # Record commit A as the stored repository state so the next parse is
    # treated as an A -> B incremental change.
    with session_scope(db) as session:
        repo = (
            session.query(RepositoryModel)
            .filter_by(remote_origin_url="mock://hybrid-delta")
            .first()
        )
        assert repo is not None
        repo.commit_hash = "A"

    # Apply working-tree changes matching the mocked diff.
    file_a_v2 = "function foo() {\n  return 1;\n}\n\nfunction baz() {\n  return 5;\n}\n"
    file_a.write_text(file_a_v2, encoding="utf-8")
    (repo_dir / "file_c.ts").write_text(
        "function gamma() { return 42; }\n", encoding="utf-8"
    )

    # Incremental parse (commit B): this is the seam run_ingest_job consumes.
    with session_scope(db) as session:
        repo = (
            session.query(RepositoryModel)
            .filter_by(remote_origin_url="mock://hybrid-delta")
            .first()
        )
        assert repo is not None
        incr_result = await parser.parse_repository(
            session=session,
            repo_path=repo_dir.as_posix(),
            repository=repo,
            new_commit_hash="B",
        )

    # The fix: the worker-visible delta must come from the result HybridParser
    # returns, and must be populated for an incremental parse.
    assert incr_result.delta is not None, (
        "HybridParser.parse_repository must expose the incremental parse delta "
        "so run_ingest_job can trigger incremental mode"
    )
    assert relp("file_a.ts") in incr_result.delta.files_modified
    assert relp("file_c.ts") in incr_result.delta.files_added
    assert incr_result.delta.definitions_added, (
        "changed definitions should be recorded on the delta"
    )

    # The old source of truth -- the module-global singleton parser -- never ran
    # a parse, so its delta is None. This is exactly why reading it was the bug.
    assert get_parser(db_manager=db).current_delta is None
