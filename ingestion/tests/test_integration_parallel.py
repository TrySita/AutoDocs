"""Integration test for parallel summary generation using real repository."""

import os
from pathlib import Path

import pytest

from database.manager import DatabaseManager
from ast_parsing.parser import parse_and_persist_repo
from ai_analysis.parallel_summaries import ParallelSummaryExecutor
from dag_builder.netx import DAGBuilder

from database.models import (
    DefinitionModel,
    FileModel,
    ReferenceModel,
)


class TestParallelIntegration:
    """Integration tests for parallel processing on real repositories."""

    @pytest.fixture
    def merchie_repo_path(self):
        """Path to the merchie test repository."""
        current_dir = Path(__file__).parent.parent
        print("current_dir:", current_dir)
        repo_path = current_dir / "test-repos" / "merchie"
        if not repo_path.exists():
            print(f"Merchie test repository not found at {repo_path}")
            pytest.skip(f"Merchie test repository not found at {repo_path}")
        return str(repo_path)

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Temporary database path for integration test."""
        return str(tmp_path / "test_integration.db")

    @pytest.mark.asyncio
    async def test_merchie_parallel_processing_levels(
        self, merchie_repo_path, temp_db_path
    ):
        """Test parallel processing levels on the merchie repository."""
        print(f"\\n📂 Testing parallel processing on: {merchie_repo_path}")

        # Parse the repository
        db_manager = DatabaseManager(db_path=temp_db_path, expire_on_commit=False)
        await parse_and_persist_repo(merchie_repo_path, db_manager=db_manager)

        with db_manager.get_session() as session:
            print(f"✅ Parsed repository:")
            print(f"   - Files: {session.query(FileModel).count()}")
            print(f"   - Definitions: {session.query(DefinitionModel).count()}")
            print(f"   - References: {session.query(ReferenceModel).count()}")

        # Build DAG and compute parallel processing levels
        dag_builder = DAGBuilder(db_manager)

        with db_manager.get_session() as session:
            definition_graph = dag_builder.build_function_dependency_graph()

        print(f"\\n🔗 Definition dependency graph:")
        print(f"   - Nodes: {definition_graph.number_of_nodes()}")
        print(f"   - Edges: {definition_graph.number_of_edges()}")

        # Create parallel executor and compute levels
        executor = ParallelSummaryExecutor(db_manager)
        definition_levels: list[list[set[int]]] = (
            executor.compute_batched_traversal_order(definition_graph)
        )

        os.system("clear")

        print(f"\\n📊 Computed {len(definition_levels)} definition processing levels:")

        # Display definition levels with actual names for manual verification
        with db_manager.get_session() as session:
            total_definitions = 0
            for i, level in enumerate(definition_levels):
                print(f"\\n  📋 Level {i} ({len(level)} definitions):")
                level_definitions = []

                for def_id_set in level[:10]:  # Show first 10 to avoid too much output
                    for def_id in def_id_set:
                        definition = (
                            session.query(DefinitionModel)
                            .filter(DefinitionModel.id == def_id)
                            .first()
                        )
                        if definition:
                            level_definitions.append(
                                {
                                    "name": definition.name,
                                    "type": definition.definition_type,
                                    "file": definition.file.file_path.split("/")[-1],
                                    "source_code": definition.source_code,
                                    "references": [
                                        call.reference_name
                                        for call in definition.references
                                        if call.reference_type != "local"
                                    ]
                                    if definition.file
                                    else "unknown",
                                }
                            )

                # Print definitions in this level
                for def_info in level_definitions:
                    print(
                        f"    - {def_info['type']} '{def_info['name']}' in {def_info['file']}\n"
                    )
                    print("Level:", i, "\n")
                    print("Referneces:", def_info["references"], "\n")

                total_definitions += len(level)

            print(f"\\n📈 Summary:")
            print(f"   - Total definitions: {total_definitions}")
            print(f"   - Processing levels: {len(definition_levels)}")
            print(
                f"   - Avg definitions per level: {total_definitions / len(definition_levels):.1f}"
            )

            # Show some dependency examples for manual verification
            print(f"\\n🔍 Dependency examples (for manual verification):")
            edges_shown = 0
            for source, target in definition_graph.edges():
                if edges_shown >= 10:  # Show first 10 edges
                    break

                source_def = (
                    session.query(DefinitionModel)
                    .filter(DefinitionModel.id == source)
                    .first()
                )
                target_def = (
                    session.query(DefinitionModel)
                    .filter(DefinitionModel.id == target)
                    .first()
                )

                if source_def and target_def:
                    source_file = (
                        source_def.file.file_path.split("/")[-1]
                        if source_def.file
                        else "unknown"
                    )
                    target_file = (
                        target_def.file.file_path.split("/")[-1]
                        if target_def.file
                        else "unknown"
                    )
                    print(
                        f"   - {source_def.name} ({source_file}) → {target_def.name} ({target_file})"
                    )
                    edges_shown += 1

            if definition_graph.number_of_edges() > 10:
                print(
                    f"   ... and {definition_graph.number_of_edges() - 10} more dependencies"
                )

        # Basic validation
        assert len(definition_levels) > 0, "Should have at least one processing level"
        assert total_definitions > 0, "Should have found definitions to process"

        # Test file-level processing as well
        file_graph = dag_builder.build_file_dependency_graph(definition_graph)
        file_levels = executor.compute_batched_traversal_order(file_graph)

        print(f"\\n📁 File processing levels: {len(file_levels)}")

        with db_manager.get_session() as session:
            for i, level in enumerate(file_levels):
                # if i >= 5:  # Show first 5 levels to avoid too much output
                #     print(f"   ... and {len(file_levels) - 5} more levels")
                #     break

                print(f"\\n  📋 File Level {i} ({len(level)} files):")
                for file_id_set in level:  # Show first 5 files per level
                    for file_id in file_id_set:
                        file_model = (
                            session.query(FileModel)
                            .filter(FileModel.id == file_id)
                            .first()
                        )
                        if file_model:
                            relative_path = file_model.file_path.replace(
                                merchie_repo_path, ""
                            ).lstrip("/")
                            print(f"    - {relative_path}")

        print(f"\\n✅ Integration test completed successfully!")
        print(f"\\n🎯 Manual verification notes:")
        print(
            f"   - Check that dependencies appear in earlier levels than their dependents"
        )
        print(f"   - Verify that related definitions are grouped logically")
        print(
            f"   - Confirm that utility/helper functions appear before their consumers"
        )


if __name__ == "__main__":
    # Run the test directly for development
    pytest.main(
        [
            __file__
            + "::TestParallelIntegration::test_merchie_parallel_processing_levels",
            "-v",
            "-s",
        ]
    )
