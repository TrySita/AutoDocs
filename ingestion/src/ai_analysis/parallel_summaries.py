"""Parallel summary generation system using definition DAG."""

import asyncio
import os
from typing import Any, Callable
from collections.abc import Coroutine
import networkx as nx
from sqlalchemy.orm import Session

from database.manager import DatabaseManager, session_scope
from database.models import DefinitionModel, FileModel
from dag_builder.netx import DAGBuilder, IdGraph
from ai_analysis.summaries import (
    generate_definition_summary_with_llm,
    generate_file_summary_with_llm,
    definition_summary_cache,
    file_summary_cache,
    clear_summary_caches,
    summaries_generated,
)
from database.types import ParseDelta


class ParallelSummaryExecutor:
    """Executor for generating summaries in parallel based on dependency order."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        max_concurrent: int = 20,
        max_requests_per_second: int = 15,
        min_batch_size: int = 50,
    ):
        """Initialize the parallel summary executor.

        Args:
            db_manager: Database manager instance
            max_concurrent: Maximum number of concurrent summary generations
        """
        self.db_manager = db_manager
        self.dag_builder = DAGBuilder(db_manager)
        self.max_concurrent = max_concurrent

        self.max_requests_per_second = int(
            os.getenv("MAX_REQUESTS_PER_SECOND", max_requests_per_second)
        )
        self.min_batch_size = min_batch_size

    def compute_batched_traversal_order(self, graph: IdGraph) -> list[list[set[int]]]:
        """Compute traversal order for definitions that enables parallelization.

        This creates "levels" where all definitions in the same level can be
        processed in parallel since they don't depend on each other.

        For summary generation, we need to process dependencies before dependents,
        so we start with nodes that have no outgoing edges (leaf nodes).

        Args:
            definition_graph: NetworkX graph of definition dependencies

        Returns:
            List of levels, where each level is a list of definition IDs
            that can be processed in parallel
        """
        # Reverse the graph to find leaf nodes first
        graph: IdGraph = graph.reverse(copy=False)

        generations: list[list[set[int]]] = []

        sccs: list[set[int]] = list(nx.strongly_connected_components(graph))

        condensed: IdGraph = nx.condensation(graph, sccs)

        node_map: dict[int, set[int]] = {i: scc for i, scc in enumerate(sccs)}

        reduced_graph: IdGraph = nx.transitive_reduction(condensed)

        for gen in nx.topological_generations(reduced_graph):
            curr: list[set[int]] = [node_map[i] for i in gen]
            generations.append(curr)

        return generations

    async def generate_definition_summary_async(
        self, definition_ids: set[int], session: Session
    ) -> None:
        """Generate summary for a single definition asynchronously.

        Note: This assumes all dependencies have already been processed
        and are available in the cache.
        """
        if len(definition_ids) > 1:
            print(
                "🔧 Generating summaries for strongly connected components:",
                definition_ids,
            )

        for definition_id in definition_ids:
            definition = (
                session.query(DefinitionModel)
                .filter(DefinitionModel.id == definition_id)
                .first()
            )

            if not definition:
                raise ValueError(f"Definition with ID {definition_id} not found")

            # Check if already in cache
            if definition_id in definition_summary_cache:
                continue

            # Check if already in database
            if definition.ai_summary:
                definition_summary_cache[definition_id] = definition.ai_summary
                continue

            print(
                f"  🔧 Generating summary for definition: {definition.name} ({definition.definition_type})"
            )

            # Verify all dependencies are available in cache
            missing_deps = []
            for ref in definition.references:
                if (
                    ref.target_definition_id
                    and not ref.target_definition_id
                    == definition.id  # Avoid self-reference
                    and ref.target_definition_id
                    not in definition_ids  # avoid strongly connected components
                    and ref.target_definition_id not in definition_summary_cache
                    and not ref.target_definition.ai_summary
                    if ref.target_definition
                    else False
                ):
                    missing_deps.append(f"reference:{ref.reference_name}")

            if missing_deps:
                raise ValueError(
                    f"Missing dependencies for {definition.name}: {missing_deps}. "
                    + "Dependencies must be processed before dependents."
                )

            # Generate summary using existing LLM function
            short_summary, full_summary = await generate_definition_summary_with_llm(
                definition
            )

            # Cache and persist
            definition_summary_cache[definition_id] = full_summary
            definition.ai_summary = full_summary
            definition.ai_short_summary = short_summary

    async def generate_file_summary_async(
        self, file_ids: set[int], session: Session
    ) -> None:
        """Generate summary for a single file asynchronously.

        Note: This assumes all definition summaries in the file are available.
        """
        for file_id in file_ids:
            file = session.query(FileModel).filter(FileModel.id == file_id).first()

            if not file:
                raise ValueError(f"File with ID {file_id} not found")

            # Check if already in cache
            if file_id in file_summary_cache:
                continue

            if not file.file_content:
                continue  # Skip files without content

            # Check if already in database
            if file.ai_summary:
                file_summary_cache[file_id] = file.ai_summary
                continue

            print(f"  📁 Generating summary for file: {file.file_path}")

            # Verify all definition summaries in this file are available
            missing_def_summaries = []
            for definition in file.definitions:
                if (
                    definition.id not in definition_summary_cache
                    and not definition.ai_summary
                ):
                    missing_def_summaries.append(definition.name)

            if missing_def_summaries:
                raise ValueError(
                    f"Missing definition summaries for file {file.file_path}: {missing_def_summaries}. "
                    + "All definitions must be summarized before the file."
                )

            # Generate summary using existing LLM function
            short_summary, full_summary = await generate_file_summary_with_llm(file)

            # Cache and persist
            file_summary_cache[file_id] = full_summary
            file.ai_summary = full_summary
            file.ai_short_summary = short_summary

    async def process_level(
        self,
        ids: list[set[int]],
        process_function: Callable[[set[int], Session], Coroutine[None, None, None]],
        session: Session,
    ) -> None:
        """Process a level of definitions in parallel using asyncio.gather with rate limiting.

        Rate limits to ~900 requests per minute (15 requests per second).
        """
        if not ids:
            return

        print(f"🔧 Processing {len(ids)} summaries in parallel with rate limiting")

        batch_size = min(self.min_batch_size, len(ids))  # Process up to 10 at once
        delay_between_batches = batch_size / self.max_requests_per_second

        total_batches = (len(ids) + batch_size - 1) // batch_size

        sem = asyncio.Semaphore(self.max_concurrent)

        # Process in batches
        for i in range(0, len(ids), batch_size):
            batch = ids[i : i + batch_size]
            print(
                f"  📦 Processing batch {i // batch_size + 1} of {total_batches} with {len(batch)} items"
            )

            async def run_one(item: set[int]) -> None:
                async with sem:
                    return await asyncio.wait_for(
                        process_function(item, session), timeout=600
                    )

            # Execute batch concurrently
            exceptions: list[BaseException | None] = await asyncio.gather(
                *[run_one(id) for id in batch], return_exceptions=True
            )

            # commit to persist changes
            session.commit()

            exceptions_to_raise = [
                exc for exc in exceptions if isinstance(exc, Exception)
            ]
            if exceptions_to_raise:
                raise ValueError(f"Error processing batch: {exceptions_to_raise}")

            global summaries_generated

            # Add delay between batches (except for the last one)
            # If 0 summaries generated, we don't need to sleep
            if i + batch_size < len(ids) and summaries_generated > 0:
                print(f"  ⏳ Waiting {delay_between_batches:.1f}s before next batch...")
                await asyncio.sleep(delay_between_batches)

    async def generate_all_summaries_parallel(
        self, definition_graph: IdGraph, file_graph: IdGraph
    ) -> dict[str, Any]:
        """Generate all summaries using parallel execution based on dependency order.

        Returns:
            Dictionary with statistics about the generation process
        """
        print("🚀 Starting parallel summary generation...")

        # Clear caches for fresh run
        clear_summary_caches()

        # Compute definition traversal levels
        definition_levels = self.compute_batched_traversal_order(definition_graph)
        print(
            f"Computed {len(definition_levels)} definition levels for parallel processing"
        )

        # Process definitions level by level
        definition_start_time = asyncio.get_event_loop().time()
        for i, level in enumerate(definition_levels):
            print(
                f"📊 Processing definition level {i + 1}/{len(definition_levels)} ({len(level)} definitions)"
            )
            with session_scope(self.db_manager) as session:
                # Process each level of definitions in parallel
                await self.process_level(
                    level, self.generate_definition_summary_async, session
                )
        definition_end_time = asyncio.get_event_loop().time()
        # Compute file traversal levels
        file_levels = self.compute_batched_traversal_order(file_graph)
        print(f"Computed {len(file_levels)} file levels for parallel processing")

        # Process files level by level
        file_start_time = asyncio.get_event_loop().time()
        for i, level in enumerate(file_levels):
            print(
                f"📊 Processing file level {i + 1}/{len(file_levels)} ({len(level)} files)"
            )
            with session_scope(self.db_manager) as session:
                await self.process_level(
                    level, self.generate_file_summary_async, session
                )
        file_end_time = asyncio.get_event_loop().time()

        # Return statistics
        return {
            "definition_levels": len(definition_levels),
            "file_levels": len(file_levels),
            "total_definitions": sum(len(level) for level in definition_levels),
            "total_files": sum(len(level) for level in file_levels),
            "definition_processing_time": definition_end_time - definition_start_time,
            "file_processing_time": file_end_time - file_start_time,
            "total_processing_time": file_end_time - definition_start_time,
            "definitions_cached": len(definition_summary_cache),
            "files_cached": len(file_summary_cache),
        }

    async def generate_incremental_summaries(self, delta: ParseDelta) -> dict[str, Any]:
        """Generate summaries only for changed items and their ancestors.

        Steps:
        - Seed from ParseDelta
        - Build definition and file subgraphs containing seeds and all parents/ancestors
        - Summarize changed definitions first, then ancestors
        - Summarize changed files first, then ancestor files
        """
        print("🚀 Starting incremental summary generation...")

        # Do NOT clear caches; we rely on previous summaries where possible

        # Seeds and subgraphs
        seed_def_ids, seed_file_ids = self.dag_builder.seeds_from_delta(delta)

        def_graph = self.dag_builder.build_function_subgraph(seed_def_ids)
        file_graph = self.dag_builder.build_file_subgraph(seed_file_ids)

        # Compute traversal levels
        def_levels = self.compute_batched_traversal_order(def_graph)
        file_levels = self.compute_batched_traversal_order(file_graph)

        # Prepare changed sets
        changed_def_ids: set[int] = set(delta.definitions_added)
        changed_file_paths: set[str] = set(
            delta.files_added
            + delta.files_modified
            + [r.new for r in delta.files_renamed]
        )

        changed_file_ids: set[int] = set()
        # Map changed file paths to IDs
        if changed_file_paths:
            with session_scope(self.db_manager) as session:
                rows = (
                    session.query(FileModel.id)
                    .filter(FileModel.file_path.in_(list(changed_file_paths)))
                    .all()
                )
                changed_file_ids = {i for (i,) in rows}

        # Helpers to filter a level list[list[set[int]]] by an allowlist
        def filter_levels(
            levels: list[list[set[int]]], allowed: set[int]
        ) -> list[list[set[int]]]:
            filtered: list[list[set[int]]] = []
            for lvl in levels:
                curr = []
                for scc in lvl:
                    keep = scc & allowed
                    if keep:
                        curr.append(keep)
                if curr:
                    filtered.append(curr)
            return filtered

        # Phase 1: Changed definitions
        changed_def_levels = (
            filter_levels(def_levels, changed_def_ids) if changed_def_ids else []
        )
        for i, level in enumerate(changed_def_levels):
            print(
                f"📊 Incremental defs (changed) level {i + 1}/{len(changed_def_levels)}: {len(level)} items"
            )
            with session_scope(self.db_manager) as session:
                await self.process_level(
                    level, self.generate_definition_summary_async, session
                )

        # Phase 2: Ancestor definitions (parents and their parents)
        ancestor_def_ids: set[int] = set(def_graph.nodes()) - changed_def_ids
        ancestor_def_levels = (
            filter_levels(def_levels, ancestor_def_ids) if ancestor_def_ids else []
        )
        for i, level in enumerate(ancestor_def_levels):
            print(
                f"📊 Incremental defs (ancestors) level {i + 1}/{len(ancestor_def_levels)}: {len(level)} items"
            )
            with session_scope(self.db_manager) as session:
                await self.process_level(
                    level, self.generate_definition_summary_async, session
                )

        # Phase 3: Changed files
        changed_file_levels = (
            filter_levels(file_levels, changed_file_ids) if changed_file_ids else []
        )
        for i, level in enumerate(changed_file_levels):
            print(
                f"📊 Incremental files (changed) level {i + 1}/{len(changed_file_levels)}: {len(level)} items"
            )
            with session_scope(self.db_manager) as session:
                await self.process_level(
                    level, self.generate_file_summary_async, session
                )

        # Phase 4: Ancestor files
        ancestor_file_ids: set[int] = set(file_graph.nodes()) - changed_file_ids
        ancestor_file_levels = (
            filter_levels(file_levels, ancestor_file_ids) if ancestor_file_ids else []
        )
        for i, level in enumerate(ancestor_file_levels):
            print(
                f"📊 Incremental files (ancestors) level {i + 1}/{len(ancestor_file_levels)}: {len(level)} items"
            )
            with session_scope(self.db_manager) as session:
                await self.process_level(
                    level, self.generate_file_summary_async, session
                )

        return {
            "def_levels_changed": len(changed_def_levels),
            "def_levels_ancestors": len(ancestor_def_levels),
            "file_levels_changed": len(changed_file_levels),
            "file_levels_ancestors": len(ancestor_file_levels),
            "defs_in_graph": def_graph.number_of_nodes(),
            "files_in_graph": file_graph.number_of_nodes(),
        }


# Convenience function for external use
async def generate_summaries_parallel(
    db_manager: DatabaseManager,
    definition_graph: IdGraph,
    file_graph: IdGraph,
    max_concurrent: int = 5,
) -> dict[str, Any]:
    """Generate all summaries using parallel execution.

    Args:
        db_manager: Database manager instance
        max_concurrent: Maximum number of concurrent operations (unused but kept for compatibility)

    Returns:
        Dictionary with generation statistics
    """
    executor = ParallelSummaryExecutor(db_manager, max_concurrent)
    return await executor.generate_all_summaries_parallel(definition_graph, file_graph)
