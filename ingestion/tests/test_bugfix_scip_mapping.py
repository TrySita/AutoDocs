"""Regression tests for SCIP symbol mapping and indexer degradation.

Covers two bugs from docs/tasks.md Part 1:

* Bug 6 -- ``SymbolMapper`` must fall back to name matching when more than one
  SCIP symbol candidate sits on a definition's start line, instead of silently
  dropping the definition.
* Bug 21 -- ``collect_repo_symbols_with_scip`` must degrade gracefully (warn and
  skip) when a language has no SCIP indexer or its indexer fails, instead of
  aborting the whole ingest, as long as at least one language was indexed.

These tests do not hit the network and do not require any SCIP tooling: the
indexer subprocess and language inference are mocked.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from ast_parsing import scip_symbol_resolution
from ast_parsing.scip_symbol_resolution import (
    ScipResult,
    ScipSymbol,
    collect_repo_symbols_with_scip,
)
from ast_parsing.symbol_mapper import SymbolMapper
from database.models import DefinitionModel, FileModel


def _make_definition(name: str, start_line: int, file_model: FileModel) -> DefinitionModel:
    """Build an in-memory DefinitionModel attached to a file (no DB session)."""
    definition = DefinitionModel(
        name=name,
        definition_type="function",
        start_line=start_line,
        end_line=start_line,
        source_code=None,
        docstring=None,
        source_code_hash=None,
    )
    definition.file = file_model
    return definition


def _make_scip_symbol(name: str, file: str, line0: int) -> ScipSymbol:
    """Build a ScipSymbol on a given 0-based start line."""
    return ScipSymbol(
        symbol=f"scip . . `{name}`.",
        name=name,
        file=file,
        range=(line0, 0, line0, 0),
        container_symbol=None,
    )


# --- Bug 6: multi-candidate name-match fallback ----------------------------


def test_multiple_candidates_on_one_line_map_by_name() -> None:
    """Two defs on the same line must each map to the SCIP symbol of same name."""
    file_model = FileModel(
        file_path="pkg/one_liner.py",
        file_content="a = 1; b = 2",
        language="python",
    )
    # Two distinct definitions on the same source line (1-based line 1).
    def_a = _make_definition("a", 1, file_model)
    def_b = _make_definition("b", 1, file_model)

    # Two SCIP candidates on the same 0-based line 0.
    sym_a = _make_scip_symbol("a", "pkg/one_liner.py", 0)
    sym_b = _make_scip_symbol("b", "pkg/one_liner.py", 0)

    mapper = SymbolMapper()
    mappings = mapper.map_definitions_to_symbols([def_a, def_b], [sym_a, sym_b])

    mapped = {m.tree_sitter_definition.name: m.scip_symbol.name for m in mappings}
    assert mapped == {"a": "a", "b": "b"}, (
        "expected both same-line definitions to map to the same-name SCIP symbol; "
        f"got {mapped}"
    )


# --- Bug 21: graceful degradation when a language cannot be indexed ---------


def test_one_unindexable_language_does_not_abort(tmp_path: Any) -> None:
    """A language whose indexer fails must be skipped, not abort the whole run.

    Python is indexed successfully (we fabricate its .scip output); ``go`` has no
    SCIP indexer wired up, so ``_index_command`` raises. The run must still
    succeed and return a ScipResult built from the Python index.
    """
    repo_root = str(tmp_path)

    def fake_run(cmd: Any, *args: Any, **kwargs: Any) -> Any:
        # The python wrap command moves an index file to out_path; emulate that
        # by writing the merge of the bash command's target path.
        joined = " ".join(cmd) if isinstance(cmd, list) else str(cmd)
        # Extract the out_path from the wrap()ed bash command and create it.
        for token in joined.replace("'", " ").split():
            if token.endswith(".scip"):
                with open(token, "wb") as fh:
                    # Minimal valid (empty) SCIP Index serialization.
                    fh.write(scip_symbol_resolution.scip_pb2.Index().SerializeToString())
        return None

    with (
        patch.object(
            scip_symbol_resolution, "_infer_languages", return_value=["go", "python"]
        ),
        patch.object(scip_symbol_resolution.subprocess, "run", side_effect=fake_run),
    ):
        result = collect_repo_symbols_with_scip(repo_root)

    assert isinstance(result, ScipResult)


def test_all_languages_unindexable_still_fails_loudly(tmp_path: Any) -> None:
    """If NO language could be indexed, the run must still raise (fail loudly)."""
    repo_root = str(tmp_path)

    with (
        patch.object(
            scip_symbol_resolution, "_infer_languages", return_value=["go"]
        ),
    ):
        with pytest.raises(RuntimeError):
            collect_repo_symbols_with_scip(repo_root)
