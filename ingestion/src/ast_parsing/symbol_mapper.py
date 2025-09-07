"""Symbol mapper to link tree-sitter definitions to SCIP symbols.

Simple line-based mapping between tree-sitter definitions and SCIP symbols.
"""

from __future__ import annotations
from dataclasses import dataclass

from .scip_symbol_resolution import ScipSymbol
from database.models import DefinitionModel


@dataclass
class SymbolMapping:
    """A mapping between a tree-sitter definition and a SCIP symbol."""

    tree_sitter_definition: DefinitionModel
    scip_symbol: ScipSymbol


class SymbolMapper:
    """Maps tree-sitter definitions to SCIP symbols using start line matching."""

    def __init__(self):
        self.mappings: list[SymbolMapping] = []

    def map_definitions_to_symbols(
        self, definitions: list[DefinitionModel], scip_symbols: list[ScipSymbol]
    ) -> list[SymbolMapping]:
        """
        Map tree-sitter definitions to SCIP symbols using start line matching.

        Strategy:
        1. Match by start line number within same file
        2. If multiple matches on same line, use name matching
        """
        mappings = []

        # Group SCIP symbols by file and start line
        symbols_by_file: dict[str, dict[int, list[ScipSymbol]]] = {}
        for symbol in scip_symbols:
            file_path = self._normalize_file_path(symbol.file)
            start_line = symbol.range[0]  # 0-based

            if file_path not in symbols_by_file:
                symbols_by_file[file_path] = {}
            if start_line not in symbols_by_file[file_path]:
                symbols_by_file[file_path][start_line] = []

            symbols_by_file[file_path][start_line].append(symbol)

        for definition in definitions:
            file_path = self._normalize_file_path(definition.file.file_path)
            start_line = definition.start_line - 1  # Convert to 0-based

            # Check if we have symbols in this file on this line
            if file_path not in symbols_by_file:
                continue
            if start_line not in symbols_by_file[file_path]:
                continue

            candidates = symbols_by_file[file_path][start_line]

            matched_symbol: ScipSymbol | None = None

            if len(candidates) == 1:
                # Single match - easy case
                matched_symbol = candidates[0]

            if matched_symbol:
                mapping = SymbolMapping(
                    tree_sitter_definition=definition, scip_symbol=matched_symbol
                )
                mappings.append(mapping)

        self.mappings = mappings
        return mappings

    def _normalize_file_path(self, file_path: str) -> str:
        """Normalize file paths for comparison."""
        # Remove leading slash and normalize
        return file_path.lstrip("/").replace("\\", "/")
