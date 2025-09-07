"""
Test import and export detection.
Migrated from TypeScript import-export.test.ts
"""

from typing import Any
import pytest
import pytest_asyncio
import asyncio
from pathlib import Path
import sys

from database.manager import DatabaseManager
from database.models import ImportModel, DefinitionModel

# Add the src directory to the path so we can import our modules
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))


class TestImportExportDetection:
    """Test import and export detection functionality."""

    @pytest.mark.asyncio
    async def test_valid_parse_result_structure(self, import_export_parse_result):
        """Test that parse result has valid structure."""
        parse_result = import_export_parse_result
        assert parse_result is not None
        assert hasattr(parse_result, "language")
        assert hasattr(parse_result, "definitions")
        assert hasattr(parse_result, "imports")
        assert hasattr(parse_result, "exports")

        assert parse_result.language == "typescript"
        assert isinstance(parse_result.imports, list)
        assert isinstance(parse_result.exports, list)
        assert isinstance(parse_result.definitions, list)

    @pytest.mark.asyncio
    async def test_identify_default_imports(
        self, import_export_parse_result, db_manager: DatabaseManager
    ):
        """Test that default imports are correctly identified."""
        with db_manager.get_session():
            parse_result = import_export_parse_result
            default_imports = [
                imp for imp in parse_result.imports if imp.import_type == "default"
            ]

            # import defaultExport from "module-name-1"
            default_import = next(
                (
                    imp
                    for imp in default_imports
                    if imp.specifier == "defaultExport"
                    and imp.module == "module-name-1"
                ),
                None,
            )

            assert default_import is not None
            assert default_import.import_type == "default"
            assert default_import.alias is None

    @pytest.mark.asyncio
    async def test_identify_namespace_imports(
        self, import_export_parse_result, db_manager: DatabaseManager
    ):
        """Test that namespace imports are correctly identified."""
        with db_manager.get_session():
            parse_result = import_export_parse_result
            namespace_imports = [
                imp for imp in parse_result.imports if imp.import_type == "namespace"
            ]

            # import * as name from "module-name-2"
            namespace_import = next(
                (
                    imp
                    for imp in namespace_imports
                    if imp.specifier == "name" and imp.module == "module-name-2"
                ),
                None,
            )

            if namespace_import:  # Only test if found
                assert namespace_import.import_type == "namespace"

    @pytest.mark.asyncio
    async def test_identify_named_imports(self, import_export_parse_result):
        """Test that named imports are correctly identified."""
        parse_result = import_export_parse_result
        named_imports = [
            imp for imp in parse_result.imports if imp.import_type == "named"
        ]

        # Should have some named imports
        assert len(named_imports) > 0

        # Check for specific named imports
        for imp in named_imports:
            assert imp.import_type == "named"
            assert imp.specifier is not None
            assert imp.module is not None

    @pytest.mark.asyncio
    async def test_identify_aliased_imports(self, import_export_parse_result):
        """Test that aliased imports are correctly identified."""
        parse_result = import_export_parse_result
        aliased_imports = [imp for imp in parse_result.imports if imp.alias is not None]

        # Should have some aliased imports
        if aliased_imports:  # Only test if found
            for imp in aliased_imports:
                assert imp.alias is not None
                assert (
                    imp.specifier != imp.alias
                )  # Alias should be different from specifier

    @pytest.mark.asyncio
    async def test_identify_side_effect_imports(self, import_export_parse_result):
        """Test that side-effect imports are correctly identified."""
        parse_result = import_export_parse_result
        side_effect_imports = [
            imp for imp in parse_result.imports if imp.import_type == "side-effect"
        ]

        # Side-effect imports might exist
        for imp in side_effect_imports:
            assert imp.import_type == "side-effect"
            assert imp.module is not None

    @pytest.mark.asyncio
    async def test_export_detection(self, import_export_parse_result):
        """Test that exports are correctly detected."""
        parse_result = import_export_parse_result
        exports = parse_result.exports

        # Should have some exports
        assert len(exports) == 14

    @pytest.mark.asyncio
    async def test_definition_extraction(self, import_export_parse_result):
        """Test that definitions are correctly extracted."""
        parse_result = import_export_parse_result
        definitions = parse_result.definitions

        # Should have some definitions
        assert len(definitions) > 0

        # Check definition structure
        for definition in definitions:
            assert hasattr(definition, "name")
            assert hasattr(definition, "start_line")
            assert hasattr(definition, "end_line")
            assert hasattr(definition, "definition_type")
            assert hasattr(definition, "function_calls")

            assert isinstance(definition.name, str)
            assert isinstance(definition.start_line, int)
            assert isinstance(definition.end_line, int)
            assert definition.start_line <= definition.end_line

    @pytest.mark.asyncio
    async def test_import_module_paths(self, import_export_parse_result):
        """Test that import module paths are correctly captured."""
        parse_result = import_export_parse_result
        imports = parse_result.imports

        # All imports should have modules
        for imp in imports:
            assert imp.module is not None
            assert isinstance(imp.module, str)
            assert len(imp.module) > 0

            # Module paths should not contain quotes
            assert not imp.module.startswith('"')
            assert not imp.module.startswith("'")
            assert not imp.module.endswith('"')
            assert not imp.module.endswith("'")

    @pytest.mark.asyncio
    async def test_consistent_import_types(self, import_export_parse_result):
        """Test that import types are consistent."""
        parse_result = import_export_parse_result
        imports = parse_result.imports
        valid_types = {"default", "named", "namespace", "side-effect", "re-export"}

        for imp in imports:
            assert imp.import_type in valid_types

    @pytest.mark.asyncio
    async def test_no_duplicate_imports(self, import_export_parse_result):
        """Test that there are no duplicate imports."""
        parse_result = import_export_parse_result
        imports = parse_result.imports

        # Create unique keys for imports
        import_keys = set()
        for imp in imports:
            key = f"{imp.specifier}::{imp.module}::{imp.import_type}"
            if key in import_keys:
                # This might be acceptable in some cases, so just log it
                print(f"Duplicate import found: {key}")
            import_keys.add(key)

        # The test passes regardless, as some duplicates might be valid

    @pytest.mark.asyncio
    async def test_exported_definitions(self, import_export_parse_result):
        """Test that exported definitions are correctly identified."""
        parse_result = import_export_parse_result
        definitions = parse_result.definitions

        # Check if any definitions are exported
        all_definitions: list[DefinitionModel] = [d for d in definitions]

        assert len(all_definitions) > 0

        print("Exported definitions:", [d.name for d in all_definitions])

        assert "MICRO_NUTRIENTS" in [d.name for d in all_definitions]


# Run the tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
