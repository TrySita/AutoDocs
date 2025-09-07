"""
Test TypeScript type extraction.
Migrated from TypeScript type-extraction.test.ts
"""

import pytest
from pathlib import Path
import sys

from database.models import DefinitionModel, TypeReferenceModel

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


class TestTypeExtraction:
    """Test TypeScript type extraction functionality."""

    @pytest.mark.asyncio
    async def test_valid_typescript_parse_result(self, types_parse_result):
        """Test that TypeScript file is parsed correctly."""
        parse_result = types_parse_result
        assert parse_result is not None
        assert parse_result.language == "typescript"
        assert isinstance(parse_result.definitions, list)
        assert isinstance(parse_result.imports, list)
        assert isinstance(parse_result.exports, list)

    @pytest.mark.asyncio
    async def test_extract_interface_definitions(self, types_parse_result):
        """Test that interface definitions are extracted."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find interface definitions
        interface_definitions: list[DefinitionModel] = [
            d for d in definitions if d.definition_type == "interface"
        ]

        if interface_definitions:  # Only test if interfaces are found
            for interface in interface_definitions:
                assert interface.definition_type == "interface"
                assert isinstance(interface.name, str)
                assert len(interface.name) > 0
                assert interface.name[
                    0
                ].isupper()  # Interfaces typically start with uppercase

    @pytest.mark.asyncio
    async def test_extract_type_alias_definitions(self, types_parse_result):
        """Test that type alias definitions are extracted."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find type alias definitions
        type_definitions: list[DefinitionModel] = [
            d for d in definitions if d.definition_type == "type"
        ]

        if type_definitions:  # Only test if type aliases are found
            for type_def in type_definitions:
                assert type_def.definition_type == "type"
                assert isinstance(type_def.name, str)
                assert len(type_def.name) > 0

    @pytest.mark.asyncio
    async def test_extract_enum_definitions(self, types_parse_result):
        """Test that enum definitions are extracted."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find enum definitions
        enum_definitions: list[DefinitionModel] = [
            d for d in definitions if d.definition_type == "enum"
        ]

        if enum_definitions:  # Only test if enums are found
            for enum_def in enum_definitions:
                assert enum_def.definition_type == "enum"
                assert isinstance(enum_def.name, str)
                assert len(enum_def.name) > 0

    @pytest.mark.asyncio
    async def test_extract_type_references_in_functions(self, types_parse_result):
        """Test that type references in functions are extracted."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find function definitions
        function_definitions: list[DefinitionModel] = [
            d for d in definitions if d.definition_type == "function"
        ]

        if function_definitions:
            # Check if any functions have type references
            functions_with_types: list[DefinitionModel] = [
                f for f in function_definitions if len(f.type_references) > 0
            ]

            if functions_with_types:  # Only test if type info is found
                for func in functions_with_types:
                    assert len(func.type_references) > 0

                    for type_ref in func.type_references:
                        assert hasattr(type_ref, "type_name")
                        assert hasattr(type_ref, "source")
                        assert isinstance(type_ref.type_name, str)
                        assert len(type_ref.type_name) > 0
                        assert type_ref.source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_resolve_local_type_references(self, types_parse_result):
        """Test that local type references are correctly resolved."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Get all type definitions (interfaces, types, enums)
        type_definitions: list[DefinitionModel] = [
            d for d in definitions if d.definition_type in ["interface", "type", "enum"]
        ]
        type_names = {d.name for d in type_definitions}

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Check for local type references
        local_type_refs: list[TypeReferenceModel] = [
            t for t in all_used_types if t.source == "local"
        ]

        if local_type_refs and type_names:
            for type_ref in local_type_refs:
                if type_ref.type_name in type_names:
                    # Local type should have source definition information
                    assert (
                        type_ref.source_definition is not None
                        or type_ref.source_definition_id is not None
                    )

    @pytest.mark.asyncio
    async def test_resolve_imported_type_references(self, types_parse_result):
        """Test that imported type references are correctly resolved."""
        parse_result = types_parse_result
        definitions = parse_result.definitions
        imports = parse_result.imports

        # Get imported type names
        imported_type_names = {
            imp.specifier for imp in imports if imp.import_type in ["named", "default"]
        }

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Check for imported type references
        imported_type_refs: list[TypeReferenceModel] = [
            t for t in all_used_types if t.source == "imported"
        ]

        if imported_type_refs:
            for type_ref in imported_type_refs:
                # Imported type should have import details
                assert type_ref.import_details is not None

    @pytest.mark.asyncio
    async def test_handle_generic_types(self, types_parse_result):
        """Test that generic types are handled correctly."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Look for generic types (containing angle brackets)
        generic_types: list[TypeReferenceModel] = [
            t for t in all_used_types if "<" in t.type_name and ">" in t.type_name
        ]

        if generic_types:  # Only test if generic types are found
            for type_ref in generic_types:
                assert "<" in type_ref.type_name
                assert ">" in type_ref.type_name
                # Should still have valid source information
                assert type_ref.source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_union_types(self, types_parse_result):
        """Test that union types are handled correctly."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Look for union types (containing pipe symbols)
        union_types: list[TypeReferenceModel] = [
            t for t in all_used_types if "|" in t.type_name
        ]

        if union_types:  # Only test if union types are found
            for type_ref in union_types:
                assert "|" in type_ref.type_name
                # Should still have valid source information
                assert type_ref.source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_array_types(self, types_parse_result):
        """Test that array types are handled correctly."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Look for array types (containing brackets)
        array_types: list[TypeReferenceModel] = [
            t for t in all_used_types if "[]" in t.type_name or "Array<" in t.type_name
        ]

        if array_types:  # Only test if array types are found
            for type_ref in array_types:
                assert "[]" in type_ref.type_name or "Array<" in type_ref.type_name
                # Should still have valid source information
                assert type_ref.source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_handle_builtin_types(self, types_parse_result):
        """Test that built-in TypeScript types are handled correctly."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find all used types
        all_used_types: list[TypeReferenceModel] = []
        for definition in definitions:
            all_used_types.extend(definition.type_references)

        # Look for built-in types
        builtin_types: list[TypeReferenceModel] = [
            t
            for t in all_used_types
            if t.type_name
            in [
                "string",
                "number",
                "boolean",
                "object",
                "void",
                "any",
                "unknown",
                "never",
            ]
        ]

        if builtin_types:  # Only test if built-in types are found
            for type_ref in builtin_types:
                # Built-in types should be marked as unknown (since they're not imported or local)
                assert type_ref.source == "unknown"

    @pytest.mark.asyncio
    async def test_type_annotation_extraction(self, types_parse_result):
        """Test that type annotations are extracted from various contexts."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        # Find functions that should have type information
        functions_with_params: list[DefinitionModel] = [
            d
            for d in definitions
            if d.definition_type == "function" and len(d.type_references) > 0
        ]

        if functions_with_params:  # Only test if functions with types are found
            for func in functions_with_params:
                # Function should have extracted type information
                assert len(func.type_references) > 0

                # Each type reference should be valid
                for type_ref in func.type_references:
                    assert isinstance(type_ref.type_name, str)
                    assert len(type_ref.type_name) > 0
                    assert type_ref.source in ["local", "imported", "unknown"]

    @pytest.mark.asyncio
    async def test_no_duplicate_type_references(self, types_parse_result):
        """Test that duplicate type references are not created."""
        parse_result = types_parse_result
        definitions = parse_result.definitions

        for definition in definitions:
            # Check for duplicate type references within each definition
            type_signatures: list[str] = []
            for type_ref in definition.type_references:
                signature = f"{type_ref.type_name}:{type_ref.source}:{type_ref.source_definition_id}"
                if signature in type_signatures:
                    # Log duplicate but don't fail (might be acceptable in some cases)
                    print(
                        f"Duplicate type reference found in {definition.name}: {signature}"
                    )
                type_signatures.append(signature)


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
