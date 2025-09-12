"""Hybrid parser combining tree-sitter AST parsing with SCIP cross-file references.

This module integrates the precise definition extraction from tree-sitter
with the cross-file reference tracking capabilities of SCIP indexing.
"""

from __future__ import annotations
from _collections_abc import dict_values
from dataclasses import dataclass, field
from typing import Optional
import os

from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ast_parsing.types import FileParseResult, ParsedASTResult

from .scip_symbol_resolution import (
    collect_repo_symbols_with_scip,
    ScipResult,
    ScipSymbol,
    ScipReference,
)
from .symbol_mapper import SymbolMapper, SymbolMapping
from .parser import ASTParser
from database.manager import DatabaseManager
from database.models import DefinitionModel, FileModel, ReferenceModel, RepositoryModel


@dataclass
class HybridDefinition:
    """Enhanced definition combining tree-sitter precision with SCIP references."""

    # Core definition from tree-sitter (authoritative)
    definition: DefinitionModel

    # SCIP enhancement data (supplementary)
    scip_symbol: Optional[ScipSymbol] = None
    cross_file_references: list[ScipReference] = field(default_factory=list)
    external_references: list[ScipReference] = field(default_factory=list)

    def __post_init__(self):
        if self.cross_file_references is None:
            self.cross_file_references = []
        if self.external_references is None:
            self.external_references = []


@dataclass
class HybridParseResult:
    """Result of hybrid parsing with both AST and SCIP data."""

    enhanced_definitions: list[HybridDefinition]
    scip_result: ScipResult
    symbol_mappings: list[SymbolMapping]
    files_processed: int
    definitions_enhanced: int  # How many tree-sitter defs got SCIP enhancements


class HybridParser:
    """Parser that combines tree-sitter AST analysis with SCIP cross-file references."""

    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.symbol_mapper = SymbolMapper()

    async def parse_repository(
        self,
        session: Session,
        repo_path: str,
        new_commit_hash: str | None = None,
        repository: RepositoryModel | None = None,
        scip_out_dir: Optional[str] = None,
    ) -> HybridParseResult:
        """
        Parse repository with both tree-sitter and SCIP, then combine results.

        Args:
            repo_path: Path to repository root
            languages: Languages to index with SCIP (if None, inferred)
            scip_out_dir: Directory for SCIP output files (if None, uses temp)

        Returns:
            HybridParseResult with enhanced definitions
        """
        print(f"[Hybrid] Starting hybrid parse of {repo_path}")

        # Step 1: Run tree-sitter AST parsing (primary source of definitions)
        print("[Hybrid] Running tree-sitter AST parsing...")
        parser = ASTParser(db_manager=self.db_manager, repository=repository)
        parsed_results = await parser.recursive_parse_directory(
            dir_path=repo_path, new_commit_hash=new_commit_hash
        )

        # Get all files that were parsed

        # Step 2: Detect workspace type and run SCIP indexing
        print("[Hybrid] Detecting workspace type...")
        workspace_type = None
        if parser.package_registry and parser.package_registry.workspace_metadata:
            workspace_type = parser.package_registry.workspace_metadata.type
            print(f"[Hybrid] Detected workspace type: {workspace_type}")
        else:
            print("[Hybrid] No workspace detected")

        print("[Hybrid] Running SCIP indexing...")
        scip_result = collect_repo_symbols_with_scip(
            repo_path,
            out_dir=scip_out_dir,
        )

        # Step 3: Load tree-sitter definitions from database
        print("[Hybrid] Loading parsed definitions...")

        definitions = self._load_parsed_definitions(parsed_results)

        # Step 4: Map tree-sitter definitions to SCIP symbols
        print(f"[Hybrid] Mapping {len(definitions)} definitions to SCIP symbols...")
        scip_symbols = self._extract_scip_symbols(scip_result)
        print(f"[Hybrid] Extracted {len(scip_symbols)} SCIP symbols")
        mappings = self.symbol_mapper.map_definitions_to_symbols(
            definitions, scip_symbols
        )

        print(
            f"[Hybrid] Successfully mapped {len(mappings)} definitions to SCIP symbols"
        )

        # Step 5: Create enhanced definitions
        enhanced_definitions = self._create_enhanced_definitions(
            definitions, mappings, scip_result
        )

        # Step 6: Create and persist references from cross-file references
        print("[Hybrid] Creating references from cross-file references...")
        self._create_references_from_scip(session, enhanced_definitions, scip_result)

        return HybridParseResult(
            enhanced_definitions=enhanced_definitions,
            scip_result=scip_result,
            symbol_mappings=mappings,
            files_processed=len(scip_result.files),
            definitions_enhanced=len(
                [d for d in enhanced_definitions if d.scip_symbol]
            ),
        )

    def _load_parsed_definitions(
        self, result: ParsedASTResult
    ) -> list[DefinitionModel]:
        """Load all definitions from the database."""
        file_results: dict_values[str, FileParseResult] = result.files.values()
        definitions: list[DefinitionModel] = [
            d for r in file_results for d in r.definitions
        ]
        return definitions

    def _extract_scip_symbols(self, scip_result: ScipResult) -> list[ScipSymbol]:
        """Extract all SCIP symbols from the result."""
        symbols = []
        for file_symbols in scip_result.files.values():
            symbols.extend(file_symbols.symbols)
        return symbols

    def _create_enhanced_definitions(
        self,
        definitions: list[DefinitionModel],
        mappings: list[SymbolMapping],
        scip_result: ScipResult,
    ) -> list[HybridDefinition]:
        """Create enhanced definitions by combining tree-sitter and SCIP data."""
        # Create mapping lookup for efficiency
        mapping_by_def_id = {
            mapping.tree_sitter_definition.id: mapping for mapping in mappings
        }

        enhanced_definitions = []

        for definition in definitions:
            mapping = mapping_by_def_id.get(definition.id)

            # Find all SCIP references that fall within this definition's range
            cross_file_refs, external_refs = self._find_references_in_definition_range(
                definition, scip_result
            )

            if mapping:
                enhanced_def = HybridDefinition(
                    definition=definition,
                    scip_symbol=mapping.scip_symbol,
                    cross_file_references=cross_file_refs,
                    external_references=external_refs,
                )
            else:
                # No SCIP mapping found but still collect references within range
                enhanced_def = HybridDefinition(
                    definition=definition,
                    cross_file_references=cross_file_refs,
                    external_references=external_refs,
                )

            enhanced_definitions.append(enhanced_def)

        return enhanced_definitions

    def _find_references_in_definition_range(
        self, definition: DefinitionModel, scip_result: ScipResult
    ) -> tuple[list[ScipReference], list[ScipReference]]:
        """
        Find all SCIP references that fall within a definition's line range.

        This correctly attributes references to their containing definitions
        and includes dependencies both within same file and cross-file.
        """
        file_path = self._normalize_path(definition.file.file_path)
        def_start = definition.start_line
        def_end = definition.end_line

        cross_file_refs = []
        external_refs = []

        # Get SCIP references for this file
        file_symbols = scip_result.files.get(file_path)

        # If no symbols for this file, return empty lists

        if not file_symbols:
            return cross_file_refs, external_refs

        # Check each SCIP reference to see if it falls within this definition
        for reference in file_symbols.references:
            ref_line = reference.range[
                0
            ]  # startLine from (startLine, startChar, endLine, endChar)

            # Check if reference is within this definition's line range
            if def_start <= ref_line <= def_end:
                # This reference originates from within this definition
                # Check where the reference points to
                target_symbol_info = scip_result.symbol_to_info.get(reference.symbol)

                if target_symbol_info:
                    target_file = target_symbol_info.file
                    target_line = target_symbol_info.range[0]

                    # If target is in different file, it's clearly a cross-file reference
                    if target_file != file_path:
                        cross_file_refs.append(reference)
                    # If target is in same file but outside this definition's range,
                    # it's still a dependency for ordering purposes
                    elif not (def_start <= target_line <= def_end):
                        cross_file_refs.append(reference)
                    # If target is within same definition range, it's internal - skip it
                else:
                    # Target symbol not found - treat as external reference
                    external_refs.append(reference)

        return cross_file_refs, external_refs

    def get_definition_references(
        self, definition: DefinitionModel, result: HybridParseResult
    ) -> list[ScipReference]:
        """Get all references (cross-file + external) for a definition."""
        for enhanced_def in result.enhanced_definitions:
            if enhanced_def.definition.id == definition.id:
                return (
                    enhanced_def.cross_file_references
                    + enhanced_def.external_references
                )
        return []

    def get_cross_file_dependencies(
        self, file_path: str, result: HybridParseResult
    ) -> list[tuple[str, str]]:
        """
        Get cross-file dependencies for a file.

        Returns:
            List of (target_file, symbol_name) tuples representing dependencies
        """
        dependencies = []

        # Find all definitions in this file
        normalized_path = self._normalize_path(file_path)
        file_definitions = [
            enhanced_def
            for enhanced_def in result.enhanced_definitions
            if self._normalize_path(enhanced_def.definition.file.file_path)
            == normalized_path
        ]

        # Collect all cross-file references
        for enhanced_def in file_definitions:
            for ref in enhanced_def.cross_file_references:
                # Find what file this reference points to
                symbol_info = result.scip_result.symbol_to_info.get(ref.symbol)
                if symbol_info:
                    dependencies.append((symbol_info.file, symbol_info.name))

        return list(set(dependencies))  # Remove duplicates

    def _normalize_path(self, path: str) -> str:
        """Normalize file path for comparison."""
        return os.path.normpath(path.lstrip("/"))

    def _create_references_from_scip(
        self,
        session: Session,
        enhanced_definitions: list[HybridDefinition],
        scip_result: ScipResult,
    ) -> None:
        """Create ReferenceModel instances from cross-file references."""
        references_created = 0

        for enhanced_def in enhanced_definitions:
            definition = enhanced_def.definition

            # Process cross-file references only - skip external ones for now
            for scip_ref in enhanced_def.cross_file_references:
                # Only consider occurrences that originate in this definition's file
                # and point to a different file (true outgoing dependency)
                if scip_ref.is_outgoing is not True:
                    continue  # skip same-file or unresolved
                # Get symbol info from SCIP result
                symbol_info = scip_result.symbol_to_info.get(scip_ref.symbol)

                target_definition = None

                if symbol_info:
                    # Try to find the target definition this reference points to
                    target_definition = self._find_target_definition(
                        symbol_info.file, symbol_info.range[0], session
                    )

                # Only create reference if we found a target definition
                if target_definition:
                    stmt = insert(ReferenceModel).values(
                        reference_name=target_definition.name,
                        reference_type="local",
                        source_definition_id=definition.id,
                        target_definition_id=target_definition.id,
                    )
                    stmt = stmt.on_conflict_do_nothing()
                    session.execute(stmt)

                    references_created += 1

        # Commit all references
        if references_created > 0:
            session.flush()
            print(
                f"[Hybrid] Created {references_created} references from cross-file references"
            )
        else:
            print(
                "[Hybrid] No references created - no matching target definitions found"
            )

    def _find_target_definition(
        self, target_file: str, target_line: int, session: Session
    ) -> DefinitionModel | None:
        """Find the target definition at the specified file and line."""
        normalized_file = self._normalize_path(target_file)

        target_definition = (
            session.query(DefinitionModel)
            .join(FileModel)
            .filter(
                FileModel.file_path.like(f"%{normalized_file}"),
                DefinitionModel.start_line <= target_line + 1,  # Convert to 1-based
                DefinitionModel.end_line >= target_line + 1,
            )
            .first()
        )

        return target_definition


def create_hybrid_parser(db_manager: DatabaseManager) -> HybridParser:
    """Factory function to create a new HybridParser instance."""
    return HybridParser(db_manager)
