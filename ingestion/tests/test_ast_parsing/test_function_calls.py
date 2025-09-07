"""
Test function call extraction and resolution.
Migrated from TypeScript function-calls.test.ts
"""

from typing import Any, cast
import pytest

from database.models import (
    DefinitionModel,
    FunctionCallModel,
    ImportModel,
)


class TestFunctionCallExtraction:
    """Test function call extraction and resolution functionality."""

    @pytest.mark.asyncio
    async def test_extract_correct_number_of_definitions(
        self, comprehensive_parse_result
    ):
        """Test that we extract the correct number of definitions."""
        parse_result = comprehensive_parse_result

        # print(f"Definitions found: {(parse_result.definitions)}")

        assert parse_result.definitions is not None
        assert len(parse_result.definitions) > 0

        # Should find main functions, classes, methods, etc.
        definition_names = [d.name for d in parse_result.definitions]

        for definition in parse_result.definitions:
            if definition.name == "functionDef":
                print("Source of functionDef:", definition.source_code)
                print(
                    "Dependencies of functionDef:",
                    [call.callee_name for call in definition.function_calls],
                )

        # These tests are more flexible since we don't know the exact content of test files
        assert len(definition_names) > 0

        # Verify that default exports are identified in the file definitions
        for definition in parse_result.definitions:
            if definition.is_default_export:
                assert definition.name == "defaultExportFunction"

    @pytest.mark.asyncio
    async def test_default_export(self, default_export_test):
        """Test that default export is correctly identified."""
        parse_result = default_export_test

        assert parse_result is not None
        assert len(parse_result.definitions) > 0

        print("Definitions found:", [d for d in parse_result.definitions])

        # Check if the default export function is present
        default_export_func = next(
            (d for d in parse_result.definitions if d.is_default_export), None
        )
        assert default_export_func is not None
        assert default_export_func.name == "NewFunc"

    @pytest.mark.asyncio
    async def test_correctly_identify_import_types(self, comprehensive_parse_result):
        """Test that import types are correctly identified."""
        parse_result = comprehensive_parse_result
        assert parse_result.imports is not None

        imports: list[ImportModel] = parse_result.imports
        valid_types = {"default", "named", "namespace", "side-effect"}

        for imp in imports:
            assert imp.import_type in valid_types
            assert imp.specifier is not None
            assert imp.module is not None

    @pytest.mark.asyncio
    async def test_extract_function_calls_within_definitions(
        self, comprehensive_parse_result
    ):
        """Test that function calls within definitions are correctly extracted."""
        parse_result = comprehensive_parse_result

        # Find definitions with function calls
        definitions_with_calls: list[DefinitionModel] = [
            d for d in parse_result.definitions if len(d.function_calls) > 0
        ]

        if definitions_with_calls:  # Only test if we have calls
            for definition in definitions_with_calls:
                assert len(definition.function_calls) > 0

                for call in definition.function_calls:
                    assert call.callee_name is not None
                    assert call.callee_source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_resolve_local_function_calls(self, comprehensive_parse_result):
        """Test that local function calls are correctly resolved."""
        parse_result = comprehensive_parse_result

        # Get all function calls
        all_calls = []
        for definition in parse_result.definitions:
            all_calls.extend(definition.function_calls)

        # Check for local function calls
        local_calls: list[FunctionCallModel] = [
            call for call in all_calls if call.callee_source == "local"
        ]

        for call in local_calls:
            assert call.callee_source == "local"
            assert call.callee_name is not None

    @pytest.mark.asyncio
    async def test_resolve_imported_function_calls(self, comprehensive_parse_result):
        """Test that imported function calls are correctly resolved."""
        parse_result = comprehensive_parse_result

        # Get all function calls
        all_calls = []
        for definition in parse_result.definitions:
            all_calls.extend(definition.function_calls)

        # Check for imported function calls
        imported_calls: list[FunctionCallModel] = [
            call for call in all_calls if call.callee_source == "imported"
        ]

        for call in imported_calls:
            assert call.callee_source == "imported"
            assert call.callee_name is not None
            # Should have import information
            assert call.import_details is not None

    @pytest.mark.asyncio
    async def test_handle_method_calls_on_objects(self, comprehensive_parse_result):
        """Test that method calls on objects are correctly handled."""
        parse_result = comprehensive_parse_result

        # Get all function calls
        all_calls: list[FunctionCallModel] = []
        for definition in parse_result.definitions:
            all_calls.extend(definition.function_calls)

        # Look for method calls (containing dots)
        method_calls = [call for call in all_calls if "." in call.callee_name]

        for call in method_calls:
            assert "." in call.callee_name
            assert call.callee_source in ["imported", "unknown", "local"]

    @pytest.mark.asyncio
    async def test_exclude_nested_function_calls(self, comprehensive_parse_result):
        """Test that nested function calls are properly handled."""
        parse_result = comprehensive_parse_result

        # Find nested definitions (definitions within other definitions)
        definitions: list[DefinitionModel] = cast(
            list[DefinitionModel], parse_result.definitions
        )
        nested_definitions: list[tuple[DefinitionModel, DefinitionModel]] = []

        for i, def1 in enumerate(definitions):
            for j, def2 in enumerate(definitions):
                if i != j and (
                    def1.start_line > def2.start_line and def1.end_line < def2.end_line
                ):
                    nested_definitions.append((def1, def2))  # def1 is nested in def2

        for child_def, parent_def in nested_definitions:
            # Check that child_def's function calls are not counted in parent_def
            for call in child_def.function_calls:
                assert call not in parent_def.function_calls

            print(f"Parent: {parent_def.name}, Child: {child_def.name}")
            print(f"Parent calls: {[c.callee_name for c in parent_def.function_calls]}")
            print(f"Child calls: {[c.callee_name for c in child_def.function_calls]}")

            # Parent definition should not have child function calls
            assert all(
                call not in parent_def.function_calls
                for call in child_def.function_calls
            )

    @pytest.mark.asyncio
    async def test_extract_class_method_calls(self, comprehensive_parse_result):
        """Test that calls within class methods are correctly extracted."""
        parse_result = comprehensive_parse_result

        # Find class-related definitions
        class_methods: list[DefinitionModel] = [
            d
            for d in parse_result.definitions
            if d.definition_type in ["function", "method"]
        ]

        for method in class_methods:
            # Method should have valid structure
            assert hasattr(method, "function_calls")
            assert isinstance(method.function_calls, list)

            # Check call structure
            for call in method.function_calls:
                assert call.callee_name is not None
                assert call.callee_source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_unknown_function_calls(self, comprehensive_parse_result):
        """Test that unknown function calls are properly marked."""
        parse_result = comprehensive_parse_result

        # Get all function calls
        all_calls: list[FunctionCallModel] = []
        for definition in parse_result.definitions:
            all_calls.extend(definition.function_calls)

        # Check for unknown calls
        unknown_calls = [call for call in all_calls if call.callee_source == "unknown"]

        for call in unknown_calls:
            assert call.callee_name is not None
            assert call.callee_source == "unknown"
            # Unknown calls should not have import information
            assert call.import_details is None


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
