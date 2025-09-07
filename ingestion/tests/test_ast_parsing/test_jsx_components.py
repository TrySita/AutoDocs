"""
Test JSX component parsing.
Migrated from TypeScript jsx-components.test.ts
"""

import pytest
from database.models import DefinitionModel, ImportModel, FunctionCallModel


class TestJSXComponentParsing:
    """Test JSX component parsing functionality."""

    @pytest.mark.asyncio
    async def test_valid_tsx_parse_result(self, jsx_parse_result):
        """Test that TSX file is parsed correctly."""
        parse_result = jsx_parse_result
        assert parse_result is not None
        assert parse_result.language == "typescript"  # TSX files use typescript parser
        assert isinstance(parse_result.definitions, list)
        assert isinstance(parse_result.imports, list)
        assert isinstance(parse_result.exports, list)

    @pytest.mark.asyncio
    async def test_extract_react_component_definitions(self, jsx_parse_result):
        """Test that React component definitions are extracted."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions
        assert len(definitions) > 0

        # Look for component definitions (functions that return JSX)
        component_definitions: list[DefinitionModel] = [
            d
            for d in definitions
            if d.definition_type in ["function", "variable"]
            and d.name[0].isupper()  # Components start with uppercase
        ]

        assert len(component_definitions) > 0

        # Check component structure
        for component in component_definitions:
            assert isinstance(component.name, str)
            assert len(component.name) > 0
            assert component.name[
                0
            ].isupper()  # React components should start with uppercase

    @pytest.mark.asyncio
    async def test_extract_jsx_element_calls(self, jsx_parse_result):
        """Test that JSX element usage is captured as function calls."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Find definitions that have function calls (should include JSX elements)
        definitions_with_calls: list[DefinitionModel] = [
            d for d in definitions if len(d.function_calls) > 0
        ]
        assert len(definitions_with_calls) > 0

        # Look for JSX-related calls
        all_calls: list[FunctionCallModel] = []
        for definition in definitions_with_calls:
            all_calls.extend(definition.function_calls)

        # Should have some calls (including JSX elements)
        assert len(all_calls) > 0

        # Check call structure
        for call in all_calls:
            assert hasattr(call, "callee_name")
            assert hasattr(call, "callee_source")
            assert call.callee_source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_react_imports(self, jsx_parse_result):
        """Test that React-related imports are correctly handled."""
        parse_result = jsx_parse_result
        imports = parse_result.imports

        # Should have React-related imports in a TSX file
        react_imports: list[ImportModel] = [
            imp
            for imp in imports
            if "react" in imp.module.lower()
            or imp.specifier in ["React", "Component", "useState", "useEffect"]
        ]

        # Might have React imports
        for imp in react_imports:
            assert imp.import_type in ["default", "named", "namespace"]
            assert isinstance(imp.specifier, str)
            assert isinstance(imp.module, str)

    @pytest.mark.asyncio
    async def test_extract_component_props(self, jsx_parse_result):
        """Test that component props are handled in type information."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Find component definitions
        components: list[DefinitionModel] = [
            d
            for d in definitions
            if d.definition_type in ["function", "variable"] and d.name[0].isupper()
        ]

        if components:
            # Components might have type information for props
            for component in components:
                # Check if type_references are populated (TSX files should have type info)
                assert hasattr(component, "type_references")
                assert isinstance(component.type_references, list)

    @pytest.mark.asyncio
    async def test_handle_jsx_fragments(self, jsx_parse_result):
        """Test that JSX fragments are handled correctly."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Look for any function calls that might represent fragments
        all_calls: list[FunctionCallModel] = []
        for definition in definitions:
            all_calls.extend(definition.function_calls)

        # Fragment usage might appear as function calls
        fragment_calls: list[FunctionCallModel] = [
            call
            for call in all_calls
            if "Fragment" in call.callee_name or call.callee_name == "React.Fragment"
        ]

        # Fragments might or might not be present, so we just check structure if they exist
        for call in fragment_calls:
            assert call.callee_source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_nested_jsx_elements(self, jsx_parse_result):
        """Test that nested JSX elements are handled correctly."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Find definitions with multiple function calls (indicating nested elements)
        nested_definitions: list[DefinitionModel] = [d for d in definitions]

        # for definition in nested_definitions:
        #     print(f"Definition: {definition.name} ({definition.id})")
        #     for call in definition.function_calls:
        #         print(f" - {call.callee_name}")

        expected_calls = [
            "React.useState",
            "View",
            "Text",
            "TouchableOpacity",
            "CustomButton",
            "CustomButton2Fake",
            "CustomButton3Fake",
            "NewComponent",
            "NEWButton",
            "incrementCount",
        ]

        for definition in nested_definitions:
            if definition.name == "HookTestComponent":
                for call in definition.function_calls:
                    assert call.callee_name in expected_calls, (
                        f"Unexpected call: {call.callee_name}"
                    )

        if nested_definitions:
            for definition in nested_definitions:
                # Should have multiple calls representing nested elements

                # All calls should have valid structure
                for call in definition.function_calls:
                    assert isinstance(call.callee_name, str)
                    assert len(call.callee_name) > 0

    @pytest.mark.asyncio
    async def test_handle_jsx_attributes(self, jsx_parse_result):
        """Test that JSX attributes don't interfere with parsing."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Should have extracted definitions successfully despite JSX attributes
        assert len(definitions) > 0

        # All definitions should have valid line numbers
        for definition in definitions:
            assert definition.start_line > 0
            assert definition.end_line >= definition.start_line

    @pytest.mark.asyncio
    async def test_handle_event_handlers(self, jsx_parse_result):
        """Test that event handlers in JSX are captured as function calls."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # Look for function calls that might be event handlers
        all_calls: list[FunctionCallModel] = []
        for definition in definitions:
            all_calls.extend(definition.function_calls)

        # Event handlers might appear as function calls
        if all_calls:
            for call in all_calls:
                # Basic structure validation
                assert isinstance(call.callee_name, str)
                assert call.callee_source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_export_jsx_components(self, jsx_parse_result):
        """Test that JSX components can be exported."""
        parse_result = jsx_parse_result
        exports = parse_result.exports

        # Should have some exports in a component file
        if exports:
            for export in exports:
                assert isinstance(export, str)
                assert len(export) > 0

    @pytest.mark.asyncio
    async def test_typescript_in_jsx(self, jsx_parse_result):
        """Test that TypeScript features work in JSX files."""
        parse_result = jsx_parse_result
        definitions = parse_result.definitions

        # TSX files should support TypeScript features
        for definition in definitions:
            # Should have type information available
            assert hasattr(definition, "type_references")

            # Function calls should be properly resolved
            for call in definition.function_calls:
                assert call.callee_source in ["local", "imported", "unknown"]
                if call.callee_source == "imported":
                    assert call.import_details is not None


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
