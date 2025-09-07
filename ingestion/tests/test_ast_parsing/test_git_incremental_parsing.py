"""Incremental parsing via mocked Git diffs.

This test verifies that when a repository has changes since the last ingested
commit, only the affected files are reparsed and the database is updated
accordingly. It covers:

- Added files
- Removed files
- Modified files (with changed definitions)
- Modified files where only the definition order changed (no logical change)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict

import pytest

from database.manager import DatabaseManager, session_scope
from database.models import FileModel, DefinitionModel, ReferenceModel
from ast_parsing.parser import parse_and_persist_repo, parse_and_persist_repo_with_delta
from dag_builder.netx import DAGBuilder
from ai_analysis.parallel_summaries import ParallelSummaryExecutor


@pytest.mark.asyncio
async def test_incremental_parsing_with_git_changes(tmp_path, monkeypatch):
    # Fresh in-memory DB isolated from session-scoped fixtures
    db = DatabaseManager(expire_on_commit=False)

    # Ensure a fresh parser instance bound to our db
    import ast_parsing.parser as parser_module

    monkeypatch.setattr(parser_module, "_global_parser", None, raising=False)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initial files
    file_a = repo_dir / "file_a.ts"
    file_b = repo_dir / "file_b.ts"
    file_rem = repo_dir / "file_rem.ts"
    ren_old = repo_dir / "ren_old.ts"

    file_a_v1 = "function foo() {\n  return 1;\n}\n\nfunction bar() {\n  return 2;\n}\n"
    file_b_v1 = (
        "function alpha() {\n  return 3;\n}\n\nfunction beta() {\n  return 4;\n}\n"
    )
    file_rem_v1 = "function toRemove() { return 0; }\n"
    ren_old_v1 = "function oldy() { return 0; }\n"

    file_a.write_text(file_a_v1, encoding="utf-8")
    file_b.write_text(file_b_v1, encoding="utf-8")
    file_rem.write_text(file_rem_v1, encoding="utf-8")
    ren_old.write_text(ren_old_v1, encoding="utf-8")

    # Helper for relative paths as stored by the parser
    def relp(name: str) -> str:
        return os.path.relpath((repo_dir / name).as_posix(), repo_dir.as_posix())

        # Mock git info to drive first (full) and second (incremental) runs

    call_counter: dict[str, int] = {"n": 0}

    def fake_extract_git_info(_repo_path: str) -> dict[str, str | None]:
        call_counter["n"] += 1
        return {
            "remote_origin_url": "mock://repo",  # used for repository identity
            "commit_hash": "A" if call_counter["n"] == 1 else "B",
            "default_branch": "main",
        }

        # Patch both in git_utils (for direct use) and in parser (imported binding)

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.extract_git_info", fake_extract_git_info
    )
    monkeypatch.setattr("ast_parsing.parser.extract_git_info", fake_extract_git_info)

    # Patch diff to only be consulted on second run. We intentionally provide
    # absolute paths for deleted/renamed to match current path handling.
    from ast_parsing.utils.git_utils import GitChanges, RenamedFile

    abs_rem = (repo_dir / "file_rem.ts").as_posix()
    abs_old = (repo_dir / "ren_old.ts").as_posix()
    abs_new = (repo_dir / "ren_new.ts").as_posix()

    def fake_compare(
        before_commit_hash: str,
        after_commit_hash: str,
        repo_path: str,
        remote_origin_url: str | None = None,
    ) -> GitChanges:
        return GitChanges(
            added=["file_c.ts"],
            modified=["file_a.ts", "file_b.ts"],
            deleted=[abs_rem],
            renamed=[RenamedFile(old=abs_old, new=abs_new)],
        )

        # Likewise, patch compare function in both modules

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.compare_commits_and_get_changed_files",
        fake_compare,
    )
    monkeypatch.setattr(
        "ast_parsing.parser.compare_commits_and_get_changed_files",
        fake_compare,
    )

    # First pass: full parse of initial state
    await parse_and_persist_repo(repo_dir.as_posix(), db)

    with session_scope(db) as session:
        # Sanity check initial files
        for expected in [
            relp("file_a.ts"),
            relp("file_b.ts"),
            relp("file_rem.ts"),
            relp("ren_old.ts"),
        ]:
            assert (
                session.query(FileModel).filter_by(file_path=expected).first()
                is not None
            ), f"Missing initial file record for {expected}"

            # Capture definition hashes for order-only-change file (file_b)
        file_b_model = (
            session.query(FileModel).filter_by(file_path=relp("file_b.ts")).first()
        )
        assert file_b_model is not None
        b_hashes_initial = {
            d.source_code_hash
            for d in session.query(DefinitionModel)
            .filter_by(file_id=file_b_model.id)
            .all()
        }

        # Apply working tree changes to match fake diff
    file_a_v2 = "function foo() {\n  return 1;\n}\n\nfunction baz() {\n  return 5;\n}\n"
    file_b_v2 = (
        # same definitions, order swapped
        "function beta() {\n  return 4;\n}\n\nfunction alpha() {\n  return 3;\n}\n"
    )
    file_c_v1 = "function gamma() { return 42; }\n"
    ren_new_v1 = ren_old_v1  # same contents after rename

    file_a.write_text(file_a_v2, encoding="utf-8")
    file_b.write_text(file_b_v2, encoding="utf-8")
    (repo_dir / "file_c.ts").write_text(file_c_v1, encoding="utf-8")
    (repo_dir / "ren_new.ts").write_text(ren_new_v1, encoding="utf-8")

    # Remove deleted file and (optionally) remove old name for rename
    os.remove(file_rem.as_posix())
    os.remove(ren_old.as_posix())

    # Second pass: incremental parsing based on mocked diff, capturing delta
    _, delta = await parse_and_persist_repo_with_delta(repo_dir.as_posix(), db)

    with session_scope(db) as session:
        # Added file present with expected definition
        file_c_model = (
            session.query(FileModel).filter_by(file_path=relp("file_c.ts")).first()
        )
        assert file_c_model is not None
        defs_c = session.query(DefinitionModel).filter_by(file_id=file_c_model.id).all()
        assert {d.name for d in defs_c} == {"gamma"}

        # Removed file is gone
        assert (
            session.query(FileModel).filter_by(file_path=relp("file_rem.ts")).first()
            is None
        )

        # Renamed file updated: old path gone, new path exists
        assert (
            session.query(FileModel).filter_by(file_path=relp("ren_old.ts")).first()
            is None
        )
        ren_new_model = (
            session.query(FileModel).filter_by(file_path=relp("ren_new.ts")).first()
        )
        assert ren_new_model is not None
        defs_ren = (
            session.query(DefinitionModel).filter_by(file_id=ren_new_model.id).all()
        )
        assert {d.name for d in defs_ren} == {"oldy"}

        # Modified file with changed definitions: bar removed, baz added, foo unchanged
        file_a_model = (
            session.query(FileModel).filter_by(file_path=relp("file_a.ts")).first()
        )
        assert file_a_model is not None
        defs_a = session.query(DefinitionModel).filter_by(file_id=file_a_model.id).all()
        names_a = {d.name for d in defs_a}
        assert names_a == {"foo", "baz"}

        # Modified file with only order change: no definition hashes changed
        file_b_model = (
            session.query(FileModel).filter_by(file_path=relp("file_b.ts")).first()
        )
        assert file_b_model is not None
        defs_b = session.query(DefinitionModel).filter_by(file_id=file_b_model.id).all()
        assert {d.name for d in defs_b} == {"alpha", "beta"}
        b_hashes_after = {d.source_code_hash for d in defs_b}
        assert b_hashes_after == b_hashes_initial, (
            "Order-only change must not alter definition set"
        )


@pytest.mark.asyncio
async def test_incremental_summaries_flow(tmp_path, monkeypatch):
    """Verify incremental summary generation calls happen in expected order using seeds/subgraphs.

    We mock LLM-bound methods and level computation to focus on orchestration.
    """
    db = DatabaseManager(expire_on_commit=False)

    # Ensure a fresh parser instance bound to our db
    import ast_parsing.parser as parser_module

    monkeypatch.setattr(parser_module, "_global_parser", None, raising=False)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Initial files
    file_a = repo_dir / "file_a.ts"
    file_b = repo_dir / "file_b.ts"

    file_a_v1 = "function foo() {\n  return 1;\n}\n\nfunction bar() {\n  return 2;\n}\n"
    file_b_v1 = (
        "function alpha() {\n  return 3;\n}\n\nfunction beta() {\n  return 4;\n}\n"
    )

    file_a.write_text(file_a_v1, encoding="utf-8")
    file_b.write_text(file_b_v1, encoding="utf-8")

    def relp(name: str) -> str:
        return os.path.relpath((repo_dir / name).as_posix(), repo_dir.as_posix())

        # Mock git info and diff similar to previous test

    call_counter: dict[str, int] = {"n": 0}

    def fake_extract_git_info(_repo_path: str) -> dict[str, str | None]:
        call_counter["n"] += 1
        return {
            "remote_origin_url": "mock://repo2",
            "commit_hash": "A" if call_counter["n"] == 1 else "B",
            "default_branch": "main",
        }

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.extract_git_info", fake_extract_git_info
    )
    monkeypatch.setattr("ast_parsing.parser.extract_git_info", fake_extract_git_info)

    from ast_parsing.utils.git_utils import GitChanges, RenamedFile

    abs_old = (repo_dir / "ren_old.ts").as_posix()
    abs_new = (repo_dir / "ren_new.ts").as_posix()

    def fake_compare(
        before_commit_hash: str,
        after_commit_hash: str,
        repo_path: str,
        remote_origin_url: str | None = None,
    ) -> GitChanges:
        return GitChanges(
            added=["file_c.ts"],
            modified=["file_a.ts"],
            deleted=[],
            renamed=[RenamedFile(old=abs_old, new=abs_new)],
        )

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.compare_commits_and_get_changed_files",
        fake_compare,
    )
    monkeypatch.setattr(
        "ast_parsing.parser.compare_commits_and_get_changed_files",
        fake_compare,
    )

    # Full parse first
    await parse_and_persist_repo(repo_dir.as_posix(), db)

    # Apply changes
    file_a_v2 = "function foo() {\n  return 1;\n}\n\nfunction baz() {\n  return 5;\n}\n"
    file_c_v1 = "function gamma() { return 42; }\n"
    ren_old_v1 = "function oldy() { return 0; }\n"

    file_a.write_text(file_a_v2, encoding="utf-8")
    (repo_dir / "file_c.ts").write_text(file_c_v1, encoding="utf-8")
    (repo_dir / "ren_new.ts").write_text(ren_old_v1, encoding="utf-8")

    # Incremental parse to get delta
    _, delta = await parse_and_persist_repo_with_delta(repo_dir.as_posix(), db)
    assert delta is not None

    # Prepare executor with mocked methods to capture calls
    executor = ParallelSummaryExecutor(db_manager=db, max_concurrent=5)

    calls: list[tuple[str, list[list[int]]]] = []

    async def fake_process_level(ids, process_function, session):  # type: ignore[no-redef]
        # Record function name and the ids passed (each element in ids is a set[int])
        materialized = [sorted(list(s)) for s in ids]
        calls.append((process_function.__name__, materialized))
        return None

    async def fake_gen_def(ids, session):  # type: ignore[no-redef]
        return None

    async def fake_gen_file(ids, session):  # type: ignore[no-redef]
        return None

    def fake_levels(graph):  # type: ignore[no-redef]
        # One level, each node as a separate SCC
        return [[{n} for n in graph.nodes()]]

    monkeypatch.setattr(executor, "process_level", fake_process_level)
    monkeypatch.setattr(executor, "generate_definition_summary_async", fake_gen_def)
    monkeypatch.setattr(executor, "generate_file_summary_async", fake_gen_file)
    monkeypatch.setattr(executor, "compute_batched_traversal_order", fake_levels)

    # Run incremental summaries
    _stats = await executor.generate_incremental_summaries(delta)

    # Assert call order: defs first, then files
    assert len(calls) >= 2
    assert calls[0][0] == fake_gen_def.__name__
    assert calls[-1][0] == fake_gen_file.__name__

    # First def call includes exactly the changed definitions (added)
    changed_def_ids = set(delta.definitions_added)
    passed_def_ids = set()
    for group in calls[0][1]:
        passed_def_ids.update(group)
    assert passed_def_ids == changed_def_ids

    # Build incremental subgraphs from delta and verify contents
    assert delta is not None
    dag_builder = DAGBuilder(db)
    seed_def_ids, seed_file_ids = dag_builder.seeds_from_delta(delta)

    with session_scope(db) as session:
        # Expected seed files: added, modified, and renamed new path (NOT unchanged files)
        expected_files = {
            relp("file_a.ts"),
            relp("file_c.ts"),
        }

        # Translate seed_file_ids back to file paths for stable assertion
        seed_files = [
            f
            for f in session.query(FileModel)
            .filter(FileModel.id.in_(list(seed_file_ids)))
            .all()
        ]
        assert set(f.file_path for f in seed_files) == expected_files

        # Seed definitions are all defs in expected files plus any directly-added IDs in delta
        expected_def_ids = set()
        for f in seed_files:
            for d in session.query(DefinitionModel).filter_by(file_id=f.id).all():
                expected_def_ids.add(d.id)
        expected_def_ids.update(delta.definitions_added)
        assert seed_def_ids == expected_def_ids

        # Function-level subgraph should contain exactly the seed definitions
    def_subgraph = dag_builder.build_function_subgraph(seed_def_ids)
    assert set(def_subgraph.nodes()) == seed_def_ids

    # File-level subgraph should contain exactly the seed files
    file_subgraph = dag_builder.build_file_subgraph(seed_file_ids)
    assert set(file_subgraph.nodes()) == seed_file_ids


@pytest.mark.asyncio
async def test_incremental_subgraphs_and_summaries_include_ancestors(
    tmp_path: Path, monkeypatch
):
    """Ensure ancestors (dependents) are included via ReferenceModel and processed after changed nodes."""
    db = DatabaseManager(expire_on_commit=False)

    # Fresh parser
    import ast_parsing.parser as parser_module

    monkeypatch.setattr(parser_module, "_global_parser", None, raising=False)

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    # Files: parent.ts depends on child.ts (ReferenceModel inserted manually)
    file_parent = repo_dir / "parent.ts"
    file_child = repo_dir / "child.ts"

    parent_v1 = "function parent() { return 0; }\n"
    child_v1 = "function child() { return 1; }\n"

    file_parent.write_text(parent_v1, encoding="utf-8")
    file_child.write_text(child_v1, encoding="utf-8")

    def relp(name: str) -> str:
        return os.path.relpath((repo_dir / name).as_posix(), repo_dir.as_posix())

        # Git info mocks A -> B

    call_counter: dict[str, int] = {"n": 0}

    def fake_extract_git_info(_repo_path: str) -> dict[str, str | None]:
        call_counter["n"] += 1
        return {
            "remote_origin_url": "mock://repo3",
            "commit_hash": "A" if call_counter["n"] == 1 else "B",
            "default_branch": "main",
        }

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.extract_git_info", fake_extract_git_info
    )
    monkeypatch.setattr("ast_parsing.parser.extract_git_info", fake_extract_git_info)

    from ast_parsing.utils.git_utils import GitChanges

    def fake_compare(
        before_commit_hash: str,
        after_commit_hash: str,
        repo_path: str,
        remote_origin_url: str | None = None,
    ) -> GitChanges:
        return GitChanges(added=[], modified=["child.ts"], deleted=[], renamed=[])

    monkeypatch.setattr(
        "ast_parsing.utils.git_utils.compare_commits_and_get_changed_files",
        fake_compare,
    )
    monkeypatch.setattr(
        "ast_parsing.parser.compare_commits_and_get_changed_files",
        fake_compare,
    )

    # Initial parse
    await parse_and_persist_repo(repo_dir.as_posix(), db)

    # Modify child to trigger incremental change
    child_v2 = "function child() { return 2; }\n"
    file_child.write_text(child_v2, encoding="utf-8")

    # Incremental parse with delta
    _, delta = await parse_and_persist_repo_with_delta(repo_dir.as_posix(), db)
    assert delta is not None

    # Insert ReferenceModel: parent (source) -> child (target)
    with session_scope(db) as session:
        parent_file = (
            session.query(FileModel).filter_by(file_path=relp("parent.ts")).first()
        )
        child_file = (
            session.query(FileModel).filter_by(file_path=relp("child.ts")).first()
        )
        assert parent_file and child_file
        parent_def = (
            session.query(DefinitionModel)
            .filter_by(file_id=parent_file.id, name="parent")
            .first()
        )
        child_def = (
            session.query(DefinitionModel)
            .filter_by(file_id=child_file.id, name="child")
            .first()
        )
        assert parent_def and child_def
        ref = ReferenceModel(
            reference_name="child",
            reference_type="local",
            source_definition=parent_def,
            target_definition=child_def,
        )
        session.add(ref)
        session.flush()

    dag_builder = DAGBuilder(db)
    seed_def_ids, seed_file_ids = dag_builder.seeds_from_delta(delta)

    # Definition subgraph should include both child (changed) and parent (ancestor)
    def_subgraph = dag_builder.build_function_subgraph(seed_def_ids)
    with session_scope(db) as session:
        # Identify ids
        parent_id = (
            session.query(DefinitionModel.id)
            .filter(DefinitionModel.name == "parent")
            .first()[0]
        )
        child_id = (
            session.query(DefinitionModel.id)
            .filter(DefinitionModel.name == "child")
            .first()[0]
        )
    assert set(def_subgraph.nodes()) == {child_id, parent_id}

    # File subgraph should include both child.ts and parent.ts
    file_subgraph = dag_builder.build_file_subgraph(seed_file_ids)
    with session_scope(db) as session:
        node_paths = {
            session.query(FileModel).filter_by(id=fid).first().file_path
            for fid in file_subgraph.nodes()
        }
        assert node_paths == {relp("child.ts"), relp("parent.ts")}

        # Now verify incremental summary phases process changed defs first, then ancestors
    executor = ParallelSummaryExecutor(db_manager=db, max_concurrent=5)

    calls: list[tuple[str, list[list[int]]]] = []

    async def fake_process_level(ids, process_function, session):  # type: ignore[no-redef]
        materialized = [sorted(list(s)) for s in ids]
        calls.append((process_function.__name__, materialized))
        return None

    async def fake_gen_def(ids, session):  # type: ignore[no-redef]
        return None

    async def fake_gen_file(ids, session):  # type: ignore[no-redef]
        return None

    def fake_levels(graph):  # type: ignore[no-redef]
        return [[{n} for n in graph.nodes()]]

    monkeypatch.setattr(executor, "process_level", fake_process_level)
    monkeypatch.setattr(executor, "generate_definition_summary_async", fake_gen_def)
    monkeypatch.setattr(executor, "generate_file_summary_async", fake_gen_file)
    monkeypatch.setattr(executor, "compute_batched_traversal_order", fake_levels)

    _ = await executor.generate_incremental_summaries(delta)

    # Expect 4 calls (defs changed, defs ancestors, files changed, files ancestors)
    assert len(calls) == 4
    assert calls[0][0] == fake_gen_def.__name__
    assert calls[1][0] == fake_gen_def.__name__
    assert calls[2][0] == fake_gen_file.__name__
    assert calls[3][0] == fake_gen_file.__name__

    # Changed defs should match delta additions; ancestor should include parent
    changed_defs = set().union(*calls[0][1])
    ancestor_defs = set().union(*calls[1][1])
    assert changed_defs == set(delta.definitions_added)
    with session_scope(db) as session:
        parent_id = (
            session.query(DefinitionModel.id)
            .filter(DefinitionModel.name == "parent")
            .first()[0]
        )
    assert ancestor_defs == {parent_id}

    # Changed files: child.ts; ancestor files: parent.ts
    with session_scope(db) as session:
        changed_file_paths = {
            session.query(FileModel)
            .filter(FileModel.id.in_(list(set().union(*calls[2][1]))))
            .first()
            .file_path
        }
        ancestor_file_paths = {
            session.query(FileModel)
            .filter(FileModel.id.in_(list(set().union(*calls[3][1]))))
            .first()
            .file_path
        }
        assert changed_file_paths == {relp("child.ts")}
        assert ancestor_file_paths == {relp("parent.ts")}
