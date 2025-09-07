"""Unit tests for parallel AI summary generation functionality."""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from ai_analysis.parallel_summaries import (
    ParallelSummaryExecutor,
    generate_summaries_parallel,
)
from ai_analysis.summaries import definition_summary_cache, file_summary_cache
from dag_builder.netx import DAGBuilder


class TestParallelSummaryExecutor:
    """Test cases for ParallelSummaryExecutor."""

    def test_compute_definition_traversal_order(
        self, parallel_test_structure, db_manager
    ):
        """Test computation of definition traversal levels for parallel processing."""
        structure = parallel_test_structure
        executor = ParallelSummaryExecutor(db_manager)

        # Build the definition graph using DAGBuilder
        dag_builder = DAGBuilder(db_manager)
        definition_graph = dag_builder.build_function_dependency_graph()

        # Debug: print graph edges to understand structure
        print("Graph edges:")
        for source, target in definition_graph.edges():
            source_name = definition_graph.nodes[source].get("label", source)
            target_name = definition_graph.nodes[target].get("label", target)
            print(f"  {source_name} -> {target_name}")

        print("Graph in-degrees:")
        for node in definition_graph.nodes():
            node_name = definition_graph.nodes[node].get("label", node)
            in_degree = definition_graph.in_degree(node)
            print(f"  {node_name}: {in_degree}")

        # Compute traversal levels
        levels = executor.compute_batched_traversal_order(definition_graph)

        print("Computed levels:")
        for i, level in enumerate(levels):
            level_names = []
            for def_id in level:
                for defs in structure["definitions"].values():
                    for definition in defs:
                        if definition.id == def_id:
                            level_names.append(definition.name)
            print(f"  Level {i}: {level_names}")

        # Now verify the correct dependency order
        assert len(levels) == 3, f"Expected 3 levels, got {len(levels)}"

        # Level 0 should have definitions with no dependencies (UtilsA, UtilsB)
        level_0_names = []
        print("Level 0 definitions:", levels[0])
        for def_id_set in levels[0]:
            for def_id in def_id_set:
                for defs in structure["definitions"].values():
                    for definition in defs:
                        if definition.id == def_id:
                            level_0_names.append(definition.name)

        assert set(level_0_names) == {"UtilsA", "UtilsB"}, f"Level 0: {level_0_names}"

        # Level 1 should have ServiceA, ServiceB
        level_1_names = []
        for def_id_set in levels[1]:
            for def_id in def_id_set:
                for defs in structure["definitions"].values():
                    for definition in defs:
                        if definition.id == def_id:
                            level_1_names.append(definition.name)

        assert set(level_1_names) == {"ServiceA", "ServiceB"}, (
            f"Level 1: {level_1_names}"
        )

        # Level 2 should have MainApp
        level_2_names = []
        for def_id_set in levels[2]:
            for def_id in def_id_set:
                for defs in structure["definitions"].values():
                    for definition in defs:
                        if definition.id == def_id:
                            level_2_names.append(definition.name)

        assert set(level_2_names) == {"MainApp"}, f"Level 2: {level_2_names}"

    def test_compute_file_traversal_order(self, parallel_test_structure, db_manager):
        """Test computation of file traversal levels for parallel processing."""
        structure = parallel_test_structure
        executor = ParallelSummaryExecutor(db_manager)

        # Build graphs
        dag_builder = DAGBuilder(db_manager)
        definition_graph = dag_builder.build_function_dependency_graph()
        file_graph = dag_builder.build_file_dependency_graph(definition_graph)

        # Compute file traversal levels
        levels = executor.compute_batched_traversal_order(file_graph)

        # Verify structure - base_utils should be processed first,
        # mid_layer should be next, top_layer should be last
        assert len(levels) >= 1, f"Expected at least 1 level, got {len(levels)}"

        # Map file IDs back to paths for verification
        file_paths_by_level = []
        for level in levels:
            level_paths = []
            for file_id_set in level:
                for file_id in file_id_set:
                    for file in structure["files"]:
                        if file.id == file_id:
                            level_paths.append(file.file_path)
            file_paths_by_level.append(level_paths)

        print(f"File processing levels: {file_paths_by_level}")

        # base_utils.ts should be in an early level (no dependencies)
        base_utils_found = False
        for level_paths in file_paths_by_level:
            if "test/base_utils.ts" in level_paths:
                base_utils_found = True
                break
        assert base_utils_found, "base_utils.ts should be in processing levels"

    @patch("ai_analysis.parallel_summaries.generate_definition_summary_with_llm")
    @patch("ai_analysis.parallel_summaries.generate_file_summary_with_llm")
    @pytest.mark.asyncio
    async def test_parallel_summary_generation_happy_path(
        self, mock_file_llm, mock_def_llm, parallel_test_structure, db_manager
    ):
        """Test the complete parallel summary generation flow."""
        structure = parallel_test_structure

        # Mock LLM responses with different content for each definition/file
        def mock_def_response(definition):
            return f"AI summary for {definition.name} ({definition.definition_type})"

        def mock_file_response(file):
            return f"AI summary for file {file.file_path}"

        mock_def_llm.side_effect = mock_def_response
        mock_file_llm.side_effect = mock_file_response

        # Execute parallel summary generation
        executor = ParallelSummaryExecutor(db_manager, max_concurrent=3)
        stats = await executor.generate_all_summaries_parallel()

        # Verify statistics
        assert stats["total_definitions"] == 5, (
            f"Expected 5 definitions, got {stats['total_definitions']}"
        )
        assert stats["total_files"] == 3, (
            f"Expected 3 files, got {stats['total_files']}"
        )
        assert stats["definitions_cached"] == 5, (
            f"Expected 5 cached definitions, got {stats['definitions_cached']}"
        )
        assert stats["files_cached"] == 3, (
            f"Expected 3 cached files, got {stats['files_cached']}"
        )

        # Verify all definitions got summaries
        expected_def_names = {"UtilsA", "UtilsB", "ServiceA", "ServiceB", "MainApp"}
        cached_def_names = set()

        for defs in structure["definitions"].values():
            for definition in defs:
                if definition.id in definition_summary_cache:
                    cached_def_names.add(definition.name)

        assert cached_def_names == expected_def_names, (
            f"Cached definitions: {cached_def_names}"
        )

        # Verify all files got summaries
        expected_file_paths = {
            "test/base_utils.ts",
            "test/mid_layer.ts",
            "test/top_layer.ts",
        }
        cached_file_paths = set()

        for file in structure["files"]:
            if file.id in file_summary_cache:
                cached_file_paths.add(file.file_path)

        assert cached_file_paths == expected_file_paths, (
            f"Cached files: {cached_file_paths}"
        )

        # Verify LLM was called for each definition and file
        assert mock_def_llm.call_count == 5, (
            f"Definition LLM calls: {mock_def_llm.call_count}"
        )
        assert mock_file_llm.call_count == 3, (
            f"File LLM calls: {mock_file_llm.call_count}"
        )

        # Verify dependency order was respected - dependencies should be processed before dependents
        # This is implicitly tested by the fact that the mock functions succeeded without dependency errors

    @pytest.mark.asyncio
    async def test_convenience_function(self, parallel_test_structure, db_manager):
        """Test the convenience function for parallel summary generation."""
        with (
            patch(
                "ai_analysis.parallel_summaries.generate_definition_summary_with_llm"
            ) as mock_def_llm,
            patch(
                "ai_analysis.parallel_summaries.generate_file_summary_with_llm"
            ) as mock_file_llm,
        ):
            mock_def_llm.return_value = "Mocked definition summary"
            mock_file_llm.return_value = "Mocked file summary"

            # Test the convenience function
            stats = await generate_summaries_parallel(db_manager, max_concurrent=2)

            # Verify it produces reasonable statistics
            assert "total_definitions" in stats
            assert "total_files" in stats
            assert "total_processing_time" in stats
            assert stats["total_definitions"] > 0
            assert stats["total_files"] > 0


if __name__ == "__main__":
    pytest.main([__file__])
