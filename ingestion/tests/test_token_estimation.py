"""Integration test for token estimation with parallel summary generation."""

import asyncio
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from database.manager import DatabaseManager
from ai_analysis.parallel_summaries import ParallelSummaryExecutor
from ai_analysis.summaries import (
    _estimate_tokens,
    _estimate_summary_tokens,
    _calculate_definition_input_tokens,
    _calculate_file_input_tokens,
)
from database.models import DefinitionModel, FileModel


class TestTokenEstimation:
    """Integration tests for token estimation on real repositories."""

    @pytest.fixture
    def merchie_db_path(self):
        """Path to the existing merchie.db database."""
        current_dir = Path(__file__).parent.parent
        db_path = current_dir / "infiscal.db"
        if not db_path.exists():
            pytest.skip(f"Merchie database not found at {db_path}")
        return str(db_path)

    @pytest.mark.asyncio
    async def test_token_estimation_integration(self, merchie_db_path):
        """Test token estimation on the real merchie database with mocked LLM calls."""
        print(f"\\n📊 Testing token estimation on: {merchie_db_path}")

        # Connect to existing database
        db_manager = DatabaseManager(db_path=merchie_db_path, expire_on_commit=False)

        # Get database statistics
        with db_manager.get_session() as session:
            total_files = session.query(FileModel).count()
            total_definitions = session.query(DefinitionModel).count()

            print(f"\\n📈 Database statistics:")
            print(f"   - Total files: {total_files}")
            print(f"   - Total definitions: {total_definitions}")

        # Track requests and tokens per level for rate limiting analysis
        level_stats = {
            "definition_levels": [],
            "file_levels": [],
            "current_def_level": 0,
            "current_file_level": 0,
            "def_level_requests": 0,
            "def_level_input_tokens": 0,
            "def_level_output_tokens": 0,
            "file_level_requests": 0,
            "file_level_input_tokens": 0,
            "file_level_output_tokens": 0,
        }

        # Mock the LLM functions with token-aware responses and tracking
        async def mock_def_summary_with_tokens(definition):
            """Mock definition summary generation with realistic token estimation."""
            input_tokens = _calculate_definition_input_tokens(
                definition,
                len(definition.function_calls) + len(definition.type_references),
            )
            output_tokens = _estimate_summary_tokens(entity_type="definition")

            # sleep to simulate LLM processing time
            # await asyncio.sleep(1)

            # Track for rate limiting analysis
            level_stats["def_level_requests"] += 1
            level_stats["def_level_input_tokens"] += input_tokens
            level_stats["def_level_output_tokens"] += output_tokens

            return f"[MOCK] Summary for {definition.name} (est. {input_tokens} input + {output_tokens} output tokens)"

        async def mock_file_summary_with_tokens(file):
            """Mock file summary generation with realistic token estimation."""
            input_tokens = _calculate_file_input_tokens(file, len(file.definitions))
            output_tokens = _estimate_summary_tokens("file")

            # sleep to simulate LLM processing time
            # await asyncio.sleep(1)

            # Track for rate limiting analysis
            level_stats["file_level_requests"] += 1
            level_stats["file_level_input_tokens"] += input_tokens
            level_stats["file_level_output_tokens"] += output_tokens

            return f"[MOCK] Summary for {file.file_path} (est. {input_tokens} input + {output_tokens} output tokens)"

        # Execute parallel summary generation with mocked LLM calls
        with (
            patch(
                "ai_analysis.parallel_summaries.generate_definition_summary_with_llm",
                new_callable=AsyncMock,
            ) as mock_def_llm,
            patch(
                "ai_analysis.parallel_summaries.generate_file_summary_with_llm",
                new_callable=AsyncMock,
            ) as mock_file_llm,
        ):
            mock_def_llm.side_effect = mock_def_summary_with_tokens
            mock_file_llm.side_effect = mock_file_summary_with_tokens

            executor = ParallelSummaryExecutor(
                db_manager=db_manager,
                max_requests_per_second=15000,
                min_batch_size=1000,
            )
            stats = await executor.generate_all_summaries_parallel()

        print(f"\\n🚀 Parallel processing completed:")
        print(f"   - Definition levels: {stats['definition_levels']}")
        print(f"   - File levels: {stats['file_levels']}")
        print(f"   - Total definitions processed: {stats['total_definitions']}")
        print(f"   - Total files processed: {stats['total_files']}")
        print(f"   - Processing time: {stats['total_processing_time']:.2f}s")

        # Analyze rate limiting impact by examining level structure
        print(f"\\n⚡ Rate limiting analysis:")

        with db_manager.get_session() as session:
            from dag_builder.netx import DAGBuilder

            dag_builder = DAGBuilder(db_manager)
            definition_graph = dag_builder.build_function_dependency_graph()
            file_graph = dag_builder.build_file_dependency_graph(definition_graph)

            # Get actual level breakdowns
            definition_levels = executor.compute_batched_traversal_order(
                definition_graph
            )
            file_levels = executor.compute_batched_traversal_order(file_graph)

            # Analyze definition levels for rate limiting
            max_concurrent_def_requests = 0
            max_def_tokens_per_level = 0

            total_requests = 0

            print(f"\\n📊 Definition levels breakdown:")
            for i, level in enumerate(definition_levels):
                level_requests = sum(len(def_id_set) for def_id_set in level)
                level_input_tokens = 0
                level_output_tokens = 0

                for def_id_set in level:
                    for def_id in def_id_set:
                        definition = (
                            session.query(DefinitionModel)
                            .filter(DefinitionModel.id == def_id)
                            .first()
                        )
                        if definition:
                            num_deps = len(definition.function_calls) + len(
                                definition.type_references
                            )
                            input_tokens = _calculate_definition_input_tokens(
                                definition, num_deps
                            )
                            output_tokens = _estimate_summary_tokens("definition")
                            level_input_tokens += input_tokens
                            level_output_tokens += output_tokens

                level_total_tokens = level_input_tokens + level_output_tokens
                max_concurrent_def_requests = max(
                    max_concurrent_def_requests, level_requests
                )
                max_def_tokens_per_level = max(
                    max_def_tokens_per_level, level_total_tokens
                )

                print(
                    f"   Level {i}: {level_requests} requests, {level_total_tokens:,} tokens"
                )

                total_requests += level_requests

            # Analyze file levels for rate limiting
            max_concurrent_file_requests = 0
            max_file_tokens_per_level = 0

            print(f"\\n📁 File levels breakdown:")
            for i, level in enumerate(file_levels):
                level_requests = sum(len(file_id_set) for file_id_set in level)
                level_input_tokens = 0
                level_output_tokens = 0

                for file_id_set in level:
                    for file_id in file_id_set:
                        file = (
                            session.query(FileModel)
                            .filter(FileModel.id == file_id)
                            .first()
                        )
                        if file:
                            input_tokens = _calculate_file_input_tokens(
                                file, len(file.definitions)
                            )
                            output_tokens = _estimate_summary_tokens("file")
                            level_input_tokens += input_tokens
                            level_output_tokens += output_tokens

                level_total_tokens = level_input_tokens + level_output_tokens
                max_concurrent_file_requests = max(
                    max_concurrent_file_requests, level_requests
                )
                max_file_tokens_per_level = max(
                    max_file_tokens_per_level, level_total_tokens
                )

                print(
                    f"   Level {i}: {level_requests} requests, {level_total_tokens:,} tokens"
                )

                total_requests += level_requests

            # Rate limiting analysis
            max_concurrent_requests = max(
                max_concurrent_def_requests, max_concurrent_file_requests
            )
            max_tokens_per_level = max(
                max_def_tokens_per_level, max_file_tokens_per_level
            )

            # OpenAI GPT-4 rate limits (conservative estimates)
            requests_per_minute = 3500
            tokens_per_minute = 90000

            print(f"\\n🚨 Rate limiting concerns:")
            print(
                f"   - Max concurrent requests in any level: {max_concurrent_requests}"
            )
            print(f"   - Max tokens in any level: {max_tokens_per_level:,}")
            print(
                f"   - OpenAI limits: {requests_per_minute} req/min, {tokens_per_minute:,} tokens/min"
            )

            if max_concurrent_requests > requests_per_minute:
                print(
                    f"   ⚠️  REQUEST RATE LIMIT RISK: Level needs {max_concurrent_requests} requests (>{requests_per_minute} limit)"
                )
                batches_needed = (
                    max_concurrent_requests + requests_per_minute - 1
                ) // requests_per_minute
                print(
                    f"      └─ Recommend splitting largest level into {batches_needed} batches"
                )
            else:
                print(f"   ✅ Request rate within limits")

            if max_tokens_per_level > tokens_per_minute:
                print(
                    f"   ⚠️  TOKEN RATE LIMIT RISK: Level needs {max_tokens_per_level:,} tokens (>{tokens_per_minute:,} limit)"
                )
                minutes_needed = max_tokens_per_level / tokens_per_minute
                print(
                    f"      └─ Would need {minutes_needed:.1f} minutes for largest level"
                )
            else:
                print(f"   ✅ Token rate within limits")

            # Provide batching recommendations
            if (
                max_concurrent_requests > requests_per_minute
                or max_tokens_per_level > tokens_per_minute
            ):
                print(f"\\n💡 Recommended batching strategy:")
                safe_request_batch_size = requests_per_minute // 2  # Conservative
                safe_token_batch_size = tokens_per_minute // 2  # Conservative

                # Calculate batch size based on most constraining factor
                request_based_batch_size = max_concurrent_requests // (
                    (max_concurrent_requests + requests_per_minute - 1)
                    // requests_per_minute
                )
                token_based_batch_size = max_tokens_per_level // (
                    (max_tokens_per_level + tokens_per_minute - 1) // tokens_per_minute
                )

                recommended_batch_size = min(
                    safe_request_batch_size,
                    request_based_batch_size,
                    safe_token_batch_size
                    // max(max_tokens_per_level // max_concurrent_requests, 1),
                )

                print(
                    f"   - Process {recommended_batch_size} items at a time within each level"
                )
                print(f"   - Add 1-2 second delays between batches")
                print(f"   - Monitor rate limit headers and adjust dynamically")

        # Calculate detailed token estimates
        total_def_input_tokens = 0
        total_def_output_tokens = 0
        total_file_input_tokens = 0
        total_file_output_tokens = 0

        # Get sample of definitions and files for detailed analysis
        with db_manager.get_session() as session:
            definitions = session.query(DefinitionModel).all()  # Sample for performance
            files = session.query(FileModel).all()  # Sample for performance

            print(
                f"\\n📊 Token estimation details (sample of {len(definitions)} definitions, {len(files)} files):"
            )

            # Estimate definition tokens
            def_token_breakdown = []
            for definition in definitions:
                num_deps = len(definition.function_calls) + len(
                    definition.type_references
                )
                input_tokens = _calculate_definition_input_tokens(definition, num_deps)
                output_tokens = _estimate_summary_tokens("definition")

                total_def_input_tokens += input_tokens
                total_def_output_tokens += output_tokens

                def_token_breakdown.append(
                    {
                        "name": definition.name,
                        "type": definition.definition_type,
                        "file": definition.file.file_path.split("/")[-1]
                        if definition.file
                        else "unknown",
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "dependencies": num_deps,
                    }
                )

            # Estimate file tokens
            file_token_breakdown = []
            for file in files:
                input_tokens = _calculate_file_input_tokens(file, len(file.definitions))
                output_tokens = _estimate_summary_tokens("file")

                total_file_input_tokens += input_tokens
                total_file_output_tokens += output_tokens

                file_token_breakdown.append(
                    {
                        "path": file.file_path,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "definitions_count": len(file.definitions),
                    }
                )

        # Show top token consumers
        print(f"\\n🔥 Top 10 definition token consumers:")
        def_token_breakdown.sort(key=lambda x: x["input_tokens"], reverse=True)
        for i, def_info in enumerate(def_token_breakdown[:10]):
            print(
                f"   {i + 1:2d}. {def_info['type']} '{def_info['name']}' in {def_info['file']}"
            )
            print(
                f"       Input: {def_info['input_tokens']:,} | Output: {def_info['output_tokens']:,} | Deps: {def_info['dependencies']}"
            )

        print(f"\\n📁 Top 10 file token consumers:")
        file_token_breakdown.sort(key=lambda x: x["input_tokens"], reverse=True)
        for i, file_info in enumerate(file_token_breakdown[:10]):
            print(f"   {i + 1:2d}. {file_info['path']}")
            print(
                f"       Input: {file_info['input_tokens']:,} | Output: {file_info['output_tokens']:,} | Defs: {file_info['definitions_count']}"
            )

        # Calculate total estimated costs
        total_input_tokens = (total_def_input_tokens + total_file_input_tokens) * 4.36363636
        total_output_tokens = (total_def_output_tokens + total_file_output_tokens) * 4.36363636
        total_tokens = total_input_tokens + total_output_tokens


        print(f"\\n💰 Estimated token costs:")
        print(f"   - Definition input tokens: {total_def_input_tokens:,}")
        print(f"   - Definition output tokens: {total_def_output_tokens:,}")
        print(f"   - File input tokens: {total_file_input_tokens:,}")
        print(f"   - File output tokens: {total_file_output_tokens:,}")
        print(f"   - Total input tokens: {total_input_tokens:,}")
        print(f"   - Total output tokens: {total_output_tokens:,}")
        print(f"   - TOTAL TOKENS: {total_tokens:,}")
        print(f"   - TOTAL REQUESTS: {total_requests:,}")

        # Analyze parallelization benefits
        avg_defs_per_level = (
            stats["total_definitions"] / stats["definition_levels"]
            if stats["definition_levels"] > 0
            else 0
        )
        avg_files_per_level = (
            stats["total_files"] / stats["file_levels"]
            if stats["file_levels"] > 0
            else 0
        )

        print(f"\\n⚡ Parallelization analysis:")
        print(f"   - Average definitions per level: {avg_defs_per_level:.1f}")
        print(f"   - Average files per level: {avg_files_per_level:.1f}")
        print(
            f"   - Parallelization potential: {max(avg_defs_per_level, avg_files_per_level):.1f}x speedup"
        )

        # Basic validation
        assert stats["total_definitions"] > 0, "Should have processed definitions"
        assert stats["total_files"] > 0, "Should have processed files"
        assert stats["definition_levels"] > 0, (
            "Should have definition processing levels"
        )
        assert stats["file_levels"] > 0, "Should have file processing levels"

        print(f"\\n✅ Token estimation integration test completed!")
        print(f"\\n🎯 Key insights:")
        print(
            f"   - Parallel processing organized into {stats['definition_levels']} definition + {stats['file_levels']} file levels"
        )
        print(
            f"   - Token usage scaled appropriately with content size and dependencies"
        )
        print(f"   - Cost estimation provides realistic budget planning for LLM usage")


if __name__ == "__main__":
    # Run the test directly for development
    pytest.main(
        [
            __file__ + "::TestTokenEstimation::test_token_estimation_integration",
            "-v",
            "-s",
        ]
    )
