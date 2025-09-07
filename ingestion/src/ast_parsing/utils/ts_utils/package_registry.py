"""
Package registry for managing package metadata and resolution.

This module provides the PackageRegistry class that manages all discovered packages
and provides methods for package lookup and entry point resolution.
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .package_discovery import PackageJsonInfo, discover_packages, WorkspaceMetadata
from .tsconfig_parser import get_path_mappings_for_file


@dataclass
class MonorepoSetupInfo:
    """Information about monorepo setup configuration."""

    type: str | None  # Type of monorepo setup performed
    workspace_manager: str | None = None  # For managed workspaces (pnpm, yarn, npm)
    synthetic_tsconfig_created: bool = False  # Whether synthetic tsconfig was created
    symlinks_created: bool = False  # Whether symlinks were created
    tsconfig_extended: bool = False  # Whether existing tsconfig was extended
    packages_referenced: list[str] = field(
        default_factory=list
    )  # List of package names/paths referenced


@dataclass
class PackageInfo:
    """Complete package information including resolved entry points and path mappings."""

    name: str | None  # Package name from package.json
    path: str  # Absolute path to package directory
    package_json_path: str  # Path to package.json file
    entry_point: str | None  # Resolved main entry point
    path_mappings: dict[str, list[str]]  # From tsconfig.json paths
    dependencies: set[str]  # All dependencies combined
    is_workspace_root: bool  # Has workspace configuration
    exports: dict[str, Any] | None  # Exports field from package.json


class PackageRegistry:
    """Registry for managing all packages in a repository."""

    def __init__(self, repo_path: str):
        self.repo_path = repo_path
        self.packages_by_name: dict[str, PackageInfo] = {}
        self.packages_by_path: dict[str, PackageInfo] = {}
        self.workspace_metadata: WorkspaceMetadata | None = None
        self.monorepo_setup_info: MonorepoSetupInfo | None = None
        self._discover_and_register_packages()
        self.monorepo_setup_info = self.setup_monorepo_configuration()

    def _discover_and_register_packages(self):
        """Discover all packages and register them in the registry."""
        package_json_infos, workspace_metadata = discover_packages(self.repo_path)
        self.workspace_metadata = workspace_metadata

        for package_json_info in package_json_infos:
            package_info = self._build_package_info(package_json_info)
            self._register_package(package_info)

    def _build_package_info(self, package_json_info: PackageJsonInfo) -> PackageInfo:
        """Build complete PackageInfo from PackageJsonInfo."""
        # Resolve entry point
        entry_point = self._resolve_entry_point(package_json_info)

        # Get path mappings from tsconfig.json
        path_mappings = get_path_mappings_for_file(package_json_info.path)

        print(f"Path mappings for package {package_json_info.name}:", path_mappings)

        return PackageInfo(
            name=package_json_info.name,
            path=package_json_info.path,
            package_json_path=package_json_info.package_json_path,
            entry_point=entry_point,
            path_mappings=path_mappings,
            dependencies=package_json_info.dependencies,
            is_workspace_root=package_json_info.is_workspace_root,
            exports=package_json_info.exports,
        )

    def _resolve_entry_point(self, package_json_info: PackageJsonInfo) -> str | None:
        """
        Resolve the main entry point for a package.

        Priority order:
        1. package.json "exports" field (. export)
        2. package.json "main" field
        3. index.ts in package root
        4. index.tsx in package root
        5. src/index.ts
        6. src/index.tsx
        """
        package_dir = Path(package_json_info.path)

        # 1. Check exports field
        if package_json_info.exports:
            exports = package_json_info.exports
            if isinstance(exports, str):
                # Simple string export
                entry_path = package_dir / exports
                if entry_path.exists():
                    return str(entry_path)
            elif isinstance(exports, dict):
                # Check for "." export
                dot_export = exports.get(".")
                if isinstance(dot_export, str):
                    entry_path = package_dir / dot_export
                    if entry_path.exists():
                        return str(entry_path)
                elif isinstance(dot_export, dict):
                    # Handle conditional exports
                    for condition in ["import", "require", "default"]:
                        if condition in dot_export and isinstance(
                            dot_export[condition], str
                        ):
                            entry_path = package_dir / dot_export[condition]
                            if entry_path.exists():
                                return str(entry_path)

        # 2. Check main field
        if package_json_info.main:
            main_path = package_dir / package_json_info.main
            if main_path.exists():
                return str(main_path)

        # 3-6. Check common index file locations
        potential_entries = [
            "index.ts",
            "index.tsx",
            "src/index.ts",
            "src/index.tsx",
            "index.js",
            "index.jsx",
        ]

        for entry in potential_entries:
            entry_path = package_dir / entry
            if entry_path.exists():
                return str(entry_path)

        return None

    def _register_package(self, package_info: PackageInfo):
        """Register a package in the lookup tables."""
        # Register by name (if it has one)
        if package_info.name:
            self.packages_by_name[package_info.name] = package_info

        # Register by path (normalized)
        normalized_path = os.path.normpath(package_info.path)
        self.packages_by_path[normalized_path] = package_info

    def has_package(self, package_name: str) -> bool:
        """Check if a package with the given name exists."""
        return package_name in self.packages_by_name

    def get_package(self, package_name: str) -> PackageInfo | None:
        """Get package info by name."""
        return self.packages_by_name.get(package_name)

    def get_package_containing_file(self, file_path: str) -> PackageInfo | None:
        """
        Find the package that contains the given file.

        Args:
            file_path: Absolute path to the file

        Returns:
            PackageInfo object or None if file is not in any package
        """
        file_path = os.path.normpath(file_path)
        best_match = None
        best_match_length = 0

        # print(f"Finding package for file: {file_path}")
        for package_path, package_info in self.packages_by_path.items():
            package_path = os.path.normpath(os.path.abspath(package_path))
            # print(f" - {package_path}: {package_info.name}")
            if file_path.startswith(package_path):
                # Check that it's a proper directory boundary
                if (
                    len(file_path) == len(package_path)
                    or file_path[len(package_path)] == os.sep
                ):
                    if len(package_path) > best_match_length:
                        best_match = package_info
                        best_match_length = len(package_path)

        return best_match

    def get_all_packages(self) -> list[PackageInfo]:
        """Get all registered packages."""
        return list(self.packages_by_path.values())

    def get_workspace_packages(self) -> list[PackageInfo]:
        """Get all packages that are not the workspace root."""
        return [
            pkg for pkg in self.packages_by_path.values() if not pkg.is_workspace_root
        ]

    def get_workspace_root(self) -> PackageInfo | None:
        """Get the workspace root package if it exists."""
        for package_info in self.packages_by_path.values():
            if package_info.is_workspace_root:
                return package_info
        return None

    def get_relative_path(self, absolute_path: str) -> str:
        """Convert absolute path to relative path from repository root."""
        return os.path.relpath(absolute_path, self.repo_path)

    def print_summary(self):
        """Print a summary of discovered packages."""
        print("\n=== Package Registry Summary ===")
        print(f"Repository: {self.repo_path}")
        print(
            f"Workspace type: {self.workspace_metadata.type if self.workspace_metadata else 'None'}"
        )
        print(f"Total packages: {len(self.packages_by_path)}")

        # Print monorepo setup information
        if self.monorepo_setup_info:
            setup_type = self.monorepo_setup_info.type
            print(f"Monorepo type: {setup_type}")
            if setup_type == "managed_workspace":
                print(
                    f"Workspace manager: {self.monorepo_setup_info.workspace_manager}"
                )
            elif setup_type == "package_based_monorepo":
                print(
                    "Created synthetic tsconfig and symlinks for package-based imports"
                )
            elif setup_type == "direct_import_monorepo":
                print("Extended tsconfig with package references for direct imports")

        workspace_root = self.get_workspace_root()
        if workspace_root:
            print(f"Workspace root: {workspace_root.name or 'unnamed'}")

        workspace_packages = self.get_workspace_packages()
        if workspace_packages:
            print("\nWorkspace packages:")
            for pkg in workspace_packages:
                relative_path = self.get_relative_path(pkg.path)
                entry_info = (
                    f" (entry: {self.get_relative_path(pkg.entry_point)})"
                    if pkg.entry_point
                    else " (no entry)"
                )
                path_mappings_info = (
                    f" (paths: {len(pkg.path_mappings)})" if pkg.path_mappings else ""
                )
                print(
                    f"  - {pkg.name or 'unnamed'} at {relative_path}{entry_info}{path_mappings_info}"
                )

        print("=== End Summary ===\n")

    def find_all_tsconfigs(self) -> list[str]:
        """
        Find all tsconfig.json files in the repository.

        Returns:
            List of absolute paths to tsconfig.json files
        """
        tsconfig_paths = []
        repo_path = Path(self.repo_path)

        # Find all tsconfig.json files, excluding node_modules
        for tsconfig_path in repo_path.rglob("tsconfig*.json"):
            # Skip files in node_modules, .git, dist, build directories
            if any(
                part in tsconfig_path.parts
                for part in ["node_modules", ".git", "dist", "build"]
            ):
                continue
            tsconfig_paths.append(str(tsconfig_path.resolve()))

        return sorted(tsconfig_paths)

    def setup_monorepo_configuration(self) -> MonorepoSetupInfo:
        """
        Setup monorepo configuration for TypeScript monorepos.

        This function handles three scenarios:
        1. pnpm/yarn workspaces (already detected) - adds workspace info to PackageInfo
        2. Package-based monorepos - creates synthetic tsconfig and symlinks
        3. Direct import monorepos - extends existing tsconfig with references

        Returns:
            MonorepoSetupInfo containing information about the monorepo setup performed
        """
        # Scenario 1: Check if we already have pnpm/yarn workspace
        # @TODO: managed workspaces have some issues with SCIP
        # if self.workspace_metadata and self.workspace_metadata.type in [
        #     "pnpm",
        #     "yarn",
        #     "npm",
        # ]:
        #     return MonorepoSetupInfo(
        #         type="managed_workspace", workspace_manager=self.workspace_metadata.type
        #     )

        packages = self.get_workspace_packages()
        if len(packages) <= 1:
            return MonorepoSetupInfo(type="single_package")

        # Scenario 2: Check for package-based monorepo
        # (packages import each other as npm packages)
        package_names = {pkg.name for pkg in packages if pkg.name}
        cross_package_dependencies = set()

        for pkg in packages:
            local_deps = pkg.dependencies.intersection(package_names)
            print(f"Package {pkg.name} local deps: {local_deps}")
            cross_package_dependencies.update(local_deps)

        if cross_package_dependencies:
            self._setup_package_based_monorepo(packages)
            return MonorepoSetupInfo(
                type="package_based_monorepo",
                synthetic_tsconfig_created=True,
                symlinks_created=True,
                packages_referenced=[
                    pkg.name or os.path.basename(pkg.path) for pkg in packages
                ],
            )

        # Scenario 3: Direct import monorepo
        # Check if packages might be importing directly from each other
        if len(packages) > 1:
            self._setup_direct_import_monorepo(packages)
            return MonorepoSetupInfo(
                type="direct_import_monorepo",
                tsconfig_extended=True,
                packages_referenced=[
                    pkg.name or os.path.basename(pkg.path) for pkg in packages
                ],
            )

        return MonorepoSetupInfo(type="unknown")

    def _setup_package_based_monorepo(self, packages: list[PackageInfo]):
        """Create synthetic tsconfig and symlinks for package-based monorepo."""
        repo_root = Path(self.repo_path)

        # Create synthetic tsconfig.json at root
        synthetic_tsconfig = {"files": [], "references": []}

        for pkg in packages:
            pkg_path = Path(pkg.path)
            relative_path = pkg_path.relative_to(repo_root)
            synthetic_tsconfig["references"].append({"path": str(relative_path)})

        self.update_tsconfig_with_references(
            repo_root / "tsconfig.json", synthetic_tsconfig["references"]
        )

        # Create node_modules with symlinks
        node_modules_dir = repo_root / "node_modules"
        node_modules_dir.mkdir(exist_ok=True)

        for pkg in packages:
            if pkg.name:
                symlink_path = node_modules_dir / pkg.name
                if not symlink_path.exists():
                    print("creating symlink:", symlink_path, "->", pkg.path)
                    symlink_path.parent.mkdir(parents=True, exist_ok=True)
                    pkg_path = Path(pkg.path)
                    symlink_path.symlink_to(pkg_path, target_is_directory=True)

    def _setup_direct_import_monorepo(self, packages: list[PackageInfo]):
        """Extend existing tsconfig or create new one with package references."""
        repo_root = Path(self.repo_path)
        tsconfig_path = repo_root / "tsconfig.json"

        # Prepare references
        references = []
        for pkg in packages:
            pkg_path = Path(pkg.path)
            relative_path = pkg_path.relative_to(repo_root)
            references.append({"path": str(relative_path)})

        self.update_tsconfig_with_references(tsconfig_path, references)

    def update_tsconfig_with_references(
        self, tsconfig_path: Path, references: list[dict[str, str]]
    ):
        """Update existing tsconfig.json to include package references."""
        if tsconfig_path.exists():
            # Extend existing tsconfig
            try:
                with open(tsconfig_path, "r", encoding="utf-8") as f:
                    existing_config = json.load(f)

                # Add references without overwriting existing fields
                existing_references = existing_config.get("references", [])
                existing_paths = {ref.get("path") for ref in existing_references}

                for ref in references:
                    if ref["path"] not in existing_paths:
                        existing_references.append(ref)

                existing_config["references"] = existing_references

                with open(tsconfig_path, "w", encoding="utf-8") as f:
                    json.dump(existing_config, f, indent=2)

            except (json.JSONDecodeError, OSError):
                # If we can't parse existing config, create new one
                self._create_new_tsconfig_with_references(tsconfig_path, references)
        else:
            # Create new tsconfig
            self._create_new_tsconfig_with_references(tsconfig_path, references)

    def _create_new_tsconfig_with_references(
        self, tsconfig_path: Path, references: list[dict[str, str]]
    ):
        """Create a new tsconfig.json with the given references."""
        new_config = {"files": [], "references": references}

        with open(tsconfig_path, "w", encoding="utf-8") as f:
            json.dump(new_config, f, indent=2)
