"""
Unit tests for enhanced PackageRegistry functionality.

Tests cover internal package dependency detection, path mapping generation,
and tsconfig consolidation for various monorepo configurations and edge cases.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from ast_parsing.utils.package_registry import PackageRegistry, PackageInfo
from ast_parsing.utils.package_discovery import PackageJsonInfo, WorkspaceMetadata


class TestPackageRegistryEnhanced:
    """Test enhanced PackageRegistry functionality for monorepo support."""

    def create_temp_repo(self, structure: dict[str, Any]) -> str:
        """Create a temporary repository structure for testing."""
        temp_dir = tempfile.mkdtemp()
        
        def create_structure(base_path: str, structure: dict):
            for name, content in structure.items():
                path = os.path.join(base_path, name)
                if isinstance(content, dict):
                    os.makedirs(path, exist_ok=True)
                    create_structure(path, content)
                else:
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, 'w', encoding='utf-8') as f:
                        f.write(content)
        
        create_structure(temp_dir, structure)
        return temp_dir

    def test_internal_package_dependencies_pnpm_workspace_protocol(self):
        """Test detection of internal dependencies with pnpm workspace: protocol."""
        # Create a mock repo with pnpm workspace dependencies
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'pnpm-workspace.yaml': 'packages:\n  - "packages/*"',
            'packages': {
                'core': {
                    'package.json': json.dumps({
                        "name": "@repo/core",
                        "dependencies": {
                            "@repo/utils": "workspace:*",
                            "external-lib": "^1.0.0"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const core = "core";'
                    }
                },
                'utils': {
                    'package.json': json.dumps({
                        "name": "@repo/utils",
                        "dependencies": {
                            "lodash": "^4.0.0"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const utils = "utils";'
                    }
                },
                'ui': {
                    'package.json': json.dumps({
                        "name": "@repo/ui",
                        "dependencies": {
                            "@repo/core": "workspace:^1.0.0",
                            "@repo/utils": "workspace:*",
                            "react": "^18.0.0"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const ui = "ui";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            internal_deps = registry.get_internal_package_dependencies()
            
            # Check that internal dependencies are detected correctly
            assert "@repo/core" in internal_deps
            assert "@repo/utils" in internal_deps["@repo/core"]
            assert "external-lib" not in internal_deps["@repo/core"]
            
            assert "@repo/ui" in internal_deps
            expected_ui_deps = {"@repo/core", "@repo/utils"}
            assert internal_deps["@repo/ui"] == expected_ui_deps
            
            # utils should not have internal deps
            assert "@repo/utils" not in internal_deps
            
        finally:
            # Clean up
            import shutil
            shutil.rmtree(temp_repo)

    def test_internal_package_dependencies_npm_star_protocol(self):
        """Test detection of internal dependencies with npm * protocol."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'core': {
                    'package.json': json.dumps({
                        "name": "@repo/core",
                        "dependencies": {
                            "@repo/utils": "*",
                            "external-lib": "^1.0.0"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const core = "core";'
                    }
                },
                'utils': {
                    'package.json': json.dumps({
                        "name": "@repo/utils",
                        "dependencies": {
                            "lodash": "*"  # This should NOT be detected as internal
                        }
                    }),
                    'src': {
                        'index.ts': 'export const utils = "utils";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            internal_deps = registry.get_internal_package_dependencies()
            
            # Check that internal dependencies are detected correctly
            assert "@repo/core" in internal_deps
            assert "@repo/utils" in internal_deps["@repo/core"]
            assert "external-lib" not in internal_deps["@repo/core"]
            
            # lodash is not an internal package, so should not be detected
            assert "@repo/utils" not in internal_deps
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_path_mappings_generation(self):
        """Test generation of TypeScript path mappings for internal packages."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'core': {
                    'package.json': json.dumps({
                        "name": "@repo/core",
                        "main": "./dist/index.js",
                        "types": "./dist/index.d.ts"
                    }),
                    'src': {
                        'index.ts': 'export const core = "core";'
                    }
                },
                'utils': {
                    'package.json': json.dumps({
                        "name": "@repo/utils"
                    }),
                    'index.ts': 'export const utils = "utils";'  # No src dir
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            path_mappings = registry.generate_path_mappings_for_internal_packages()
            
            # Check that path mappings point to package directories
            assert "@repo/core" in path_mappings
            assert path_mappings["@repo/core"] == ["packages/core"]
            
            assert "@repo/core/*" in path_mappings
            assert path_mappings["@repo/core/*"] == ["packages/core/*"]
            
            # utils package mapping
            assert "@repo/utils" in path_mappings
            assert path_mappings["@repo/utils"] == ["packages/utils"]
            
            assert "@repo/utils/*" in path_mappings
            assert path_mappings["@repo/utils/*"] == ["packages/utils/*"]
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_consolidate_tsconfig_with_path_mappings(self):
        """Test tsconfig consolidation includes path mappings."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'core': {
                    'package.json': json.dumps({
                        "name": "@repo/core",
                        "dependencies": {
                            "@repo/utils": "workspace:*"
                        }
                    }),
                    'src': {
                        'index.ts': 'import { utils } from "@repo/utils"; export const core = utils;'
                    }
                },
                'utils': {
                    'package.json': json.dumps({
                        "name": "@repo/utils"
                    }),
                    'src': {
                        'index.ts': 'export const utils = "utils";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            result = registry.consolidate_tsconfig_for_monorepo()
            
            assert result is True
            
            # Check that tsconfig.json was created
            tsconfig_path = os.path.join(temp_repo, 'tsconfig.json')
            assert os.path.exists(tsconfig_path)
            
            # Read and verify the generated config
            with open(tsconfig_path, 'r') as f:
                config = json.load(f)
            
            # Check basic structure
            assert "compilerOptions" in config
            assert "baseUrl" in config["compilerOptions"]
            assert config["compilerOptions"]["baseUrl"] == "."
            
            # Check that path mappings were included
            assert "paths" in config["compilerOptions"]
            paths = config["compilerOptions"]["paths"]
            
            assert "@repo/core" in paths
            assert "@repo/utils" in paths
            assert "@repo/core/*" in paths
            assert "@repo/utils/*" in paths
            
            # Check include patterns
            assert "include" in config
            assert len(config["include"]) > 0
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_consolidate_tsconfig_preserves_existing_config(self):
        """Test that existing tsconfig is backed up and extended."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'tsconfig.json': json.dumps({
                "compilerOptions": {
                    "strict": True,
                    "target": "ES2020"
                }
            }),
            'packages': {
                'core': {
                    'package.json': json.dumps({
                        "name": "@repo/core"
                    }),
                    'src': {
                        'index.ts': 'export const core = "core";'
                    }
                },
                'utils': {
                    'package.json': json.dumps({
                        "name": "@repo/utils"
                    }),
                    'src': {
                        'index.ts': 'export const utils = "utils";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            result = registry.consolidate_tsconfig_for_monorepo()
            
            assert result is True
            
            # Check that backup was created
            backup_path = os.path.join(temp_repo, 'tsconfig.prev.json')
            assert os.path.exists(backup_path)
            
            # Check that new config extends the backup
            tsconfig_path = os.path.join(temp_repo, 'tsconfig.json')
            with open(tsconfig_path, 'r') as f:
                config = json.load(f)
            
            assert "extends" in config
            assert config["extends"] == "./tsconfig.prev.json"
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_single_package_repo_skips_consolidation(self):
        """Test that single-package repos skip consolidation."""
        structure = {
            'package.json': json.dumps({
                "name": "single-package",
                "private": True
            }),
            'src': {
                'index.ts': 'export const app = "app";'
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            result = registry.consolidate_tsconfig_for_monorepo()
            
            # Should skip consolidation for single package
            assert result is False
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_mixed_dependency_protocols(self):
        """Test handling of mixed workspace and npm dependency protocols."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'mixed': {
                    'package.json': json.dumps({
                        "name": "@repo/mixed",
                        "dependencies": {
                            "@repo/workspace-dep": "workspace:*",
                            "@repo/npm-dep": "*",
                            "external": "^1.0.0",
                            "@repo/nonexistent": "*"  # This package doesn't exist
                        }
                    }),
                    'src': {
                        'index.ts': 'export const mixed = "mixed";'
                    }
                },
                'workspace-dep': {
                    'package.json': json.dumps({
                        "name": "@repo/workspace-dep"
                    }),
                    'src': {
                        'index.ts': 'export const workspaceDep = "workspaceDep";'
                    }
                },
                'npm-dep': {
                    'package.json': json.dumps({
                        "name": "@repo/npm-dep"
                    }),
                    'src': {
                        'index.ts': 'export const npmDep = "npmDep";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            internal_deps = registry.get_internal_package_dependencies()
            
            # Check that both workspace: and * protocols are detected
            assert "@repo/mixed" in internal_deps
            expected_deps = {"@repo/workspace-dep", "@repo/npm-dep"}
            assert internal_deps["@repo/mixed"] == expected_deps
            
            # nonexistent package should not be included
            assert "@repo/nonexistent" not in internal_deps["@repo/mixed"]
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_scoped_and_unscoped_packages(self):
        """Test handling of both scoped and unscoped package names."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'scoped': {
                    'package.json': json.dumps({
                        "name": "@org/scoped",
                        "dependencies": {
                            "unscoped": "workspace:*",
                            "@org/another": "workspace:*"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const scoped = "scoped";'
                    }
                },
                'unscoped': {
                    'package.json': json.dumps({
                        "name": "unscoped"
                    }),
                    'src': {
                        'index.ts': 'export const unscoped = "unscoped";'
                    }
                },
                'another': {
                    'package.json': json.dumps({
                        "name": "@org/another"
                    }),
                    'src': {
                        'index.ts': 'export const another = "another";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            internal_deps = registry.get_internal_package_dependencies()
            path_mappings = registry.generate_path_mappings_for_internal_packages()
            
            # Check internal dependencies
            assert "@org/scoped" in internal_deps
            expected_deps = {"unscoped", "@org/another"}
            assert internal_deps["@org/scoped"] == expected_deps
            
            # Check path mappings for both scoped and unscoped
            assert "@org/scoped" in path_mappings
            assert "unscoped" in path_mappings
            assert "@org/another" in path_mappings
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_packages_with_different_entry_points(self):
        """Test path mappings for packages with various configurations."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'with-main': {
                    'package.json': json.dumps({
                        "name": "@repo/with-main",
                        "main": "./lib/custom.js"
                    }),
                    'lib': {
                        'custom.ts': 'export const custom = "custom";'
                    }
                },
                'with-exports': {
                    'package.json': json.dumps({
                        "name": "@repo/with-exports",
                        "exports": {
                            ".": "./dist/index.js"
                        }
                    }),
                    'dist': {
                        'index.ts': 'export const exports = "exports";'
                    }
                },
                'default-structure': {
                    'package.json': json.dumps({
                        "name": "@repo/default"
                    }),
                    'src': {
                        'index.ts': 'export const defaultPkg = "default";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            registry = PackageRegistry(temp_repo)
            path_mappings = registry.generate_path_mappings_for_internal_packages()
            
            # Check that path mappings point to package directories
            assert "@repo/with-main" in path_mappings
            main_mapping = path_mappings["@repo/with-main"][0]
            assert main_mapping == "packages/with-main"
            
            assert "@repo/with-exports" in path_mappings  
            exports_mapping = path_mappings["@repo/with-exports"][0]
            assert exports_mapping == "packages/with-exports"
            
            assert "@repo/default" in path_mappings
            default_mapping = path_mappings["@repo/default"][0]
            assert default_mapping == "packages/default-structure"
            
            # Check that subpath mappings exist
            assert "@repo/with-main/*" in path_mappings
            assert path_mappings["@repo/with-main/*"] == ["packages/with-main/*"]
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)

    def test_error_handling_malformed_package_json(self):
        """Test graceful handling of malformed package.json files."""
        structure = {
            'package.json': json.dumps({
                "name": "monorepo",
                "private": True,
                "workspaces": ["packages/*"]
            }),
            'packages': {
                'valid': {
                    'package.json': json.dumps({
                        "name": "@repo/valid",
                        "dependencies": {
                            "@repo/invalid": "workspace:*"
                        }
                    }),
                    'src': {
                        'index.ts': 'export const valid = "valid";'
                    }
                },
                'invalid': {
                    'package.json': '{ "name": "@repo/invalid", malformed json',  # Invalid JSON
                    'src': {
                        'index.ts': 'export const invalid = "invalid";'
                    }
                }
            }
        }
        
        temp_repo = self.create_temp_repo(structure)
        
        try:
            # This should not crash despite malformed JSON
            registry = PackageRegistry(temp_repo)
            internal_deps = registry.get_internal_package_dependencies()
            
            # Valid package should still be processed
            assert "@repo/valid" in internal_deps
            
        finally:
            import shutil
            shutil.rmtree(temp_repo)