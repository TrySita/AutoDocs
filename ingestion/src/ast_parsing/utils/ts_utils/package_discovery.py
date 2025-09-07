"""
Package discovery utilities for monorepo analysis.

This module provides functionality to discover packages in a repository by finding
all package.json files and extracting package metadata.
"""

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class WorkspaceMetadata:
    """Metadata about the workspace configuration."""
    type: str | None  # pnpm, turbo, yarn, npm, lerna, rush
    config_file: str | None  # Path to workspace config file
    patterns: list[str]  # Workspace patterns if available


@dataclass
class PackageJsonInfo:
    """Information extracted from a package.json file."""
    name: str | None  # Package name from package.json
    path: str  # Absolute path to package directory
    package_json_path: str  # Path to package.json file
    main: str | None  # Main entry point
    exports: dict[str, Any] | None  # Exports field
    dependencies: set[str]  # All dependencies combined
    is_workspace_root: bool  # Has workspace configuration


def find_all_package_json_files(repo_path: str) -> list[str]:
    """
    Find all package.json files in the repository, excluding common non-package directories.
    
    Args:
        repo_path: Root path of the repository
        
    Returns:
        List of absolute paths to package.json files
    """
    package_json_files = []
    excluded_dirs = {
        'node_modules', '.git', '.next', 'dist', 'build', 'out', 'coverage',
        '.turbo', '.vscode', '.idea', '__pycache__', '.pytest_cache',
        'target', 'vendor', '.gradle', '.m2'
    }
    
    repo_path_obj = Path(repo_path)
    
    for root, dirs, files in os.walk(repo_path):
        # Remove excluded directories from the search
        dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('.')]
        
        if 'package.json' in files:
            package_json_path = os.path.join(root, 'package.json')
            package_json_files.append(package_json_path)
    
    return package_json_files


def parse_package_json(package_json_path: str) -> PackageJsonInfo | None:
    """
    Parse a package.json file and extract relevant information.
    
    Args:
        package_json_path: Path to the package.json file
        
    Returns:
        PackageJsonInfo object or None if parsing fails
    """
    try:
        with open(package_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(f"Warning: Could not parse {package_json_path}: {e}")
        return None
    
    package_dir = os.path.dirname(package_json_path)
    
    # Extract dependencies
    dependencies = set()
    for dep_type in ['dependencies', 'devDependencies', 'peerDependencies', 'optionalDependencies']:
        deps = data.get(dep_type, {})
        if isinstance(deps, dict):
            dependencies.update(deps.keys())
    
    # Workspace root detection will be handled in discover_packages
    is_workspace_root = False
    
    return PackageJsonInfo(
        name=data.get('name'),
        path=package_dir,
        package_json_path=package_json_path,
        main=data.get('main'),
        exports=data.get('exports') if isinstance(data.get('exports'), dict) else None,
        dependencies=dependencies,
        is_workspace_root=is_workspace_root
    )


def detect_workspace_metadata(repo_path: str) -> WorkspaceMetadata:
    """
    Detect workspace configuration metadata (for informational purposes).
    
    Args:
        repo_path: Root path of the repository
        
    Returns:
        WorkspaceMetadata object with detected workspace information
    """
    repo_path_obj = Path(repo_path)
    
    # Check for pnpm workspace
    pnpm_workspace = repo_path_obj / 'pnpm-workspace.yaml'
    if pnpm_workspace.exists():
        try:
            import yaml
            with open(pnpm_workspace, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                patterns = data.get('packages', []) if isinstance(data, dict) else []
                return WorkspaceMetadata('pnpm', str(pnpm_workspace), patterns)
        except Exception:
            return WorkspaceMetadata('pnpm', str(pnpm_workspace), [])
    
    # Check for turbo.json
    turbo_json = repo_path_obj / 'turbo.json'
    if turbo_json.exists():
        return WorkspaceMetadata('turbo', str(turbo_json), [])
    
    # Check for lerna.json
    lerna_json = repo_path_obj / 'lerna.json'
    if lerna_json.exists():
        try:
            with open(lerna_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                patterns = data.get('packages', []) if isinstance(data, dict) else []
                return WorkspaceMetadata('lerna', str(lerna_json), patterns)
        except Exception:
            return WorkspaceMetadata('lerna', str(lerna_json), [])
    
    # Check for rush.json
    rush_json = repo_path_obj / 'rush.json'
    if rush_json.exists():
        return WorkspaceMetadata('rush', str(rush_json), [])
    
    # Check root package.json for workspaces
    root_package_json = repo_path_obj / 'package.json'
    if root_package_json.exists():
        try:
            with open(root_package_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
                workspaces = data.get('workspaces')
                if workspaces:
                    patterns = workspaces if isinstance(workspaces, list) else workspaces.get('packages', [])
                    package_manager = 'yarn' if 'yarn.lock' in os.listdir(repo_path) else 'npm'
                    return WorkspaceMetadata(package_manager, str(root_package_json), patterns)
        except Exception:
            pass
    
    return WorkspaceMetadata(None, None, [])


def discover_packages(repo_path: str) -> tuple[list[PackageJsonInfo], WorkspaceMetadata]:
    """
    Discover all packages in a repository using package.json files as source of truth.
    
    Args:
        repo_path: Root path of the repository
        
    Returns:
        Tuple of (list of PackageJsonInfo objects, WorkspaceMetadata)
    """
    print(f"Discovering packages in repository: {repo_path}")
    
    # Find all package.json files
    package_json_files = find_all_package_json_files(repo_path)
    print(f"Found {len(package_json_files)} package.json files")
    
    # Parse each package.json file
    packages: list[PackageJsonInfo] = []
    for package_json_path in package_json_files:
        package_info: PackageJsonInfo | None = parse_package_json(package_json_path)
        if package_info:
            packages.append(package_info)
            print(f"Discovered package: {package_info.name or 'unnamed'} at {package_info.path}")
    
    # Find the workspace root - the package.json highest up in the directory tree
    # that has workspace configuration
    workspace_root_path = None
    shortest_path_len = float('inf')
    
    for package in packages:
        # Check if this package has workspace configuration
        try:
            with open(package.package_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                has_workspaces = 'workspaces' in data
                
            if has_workspaces:
                workspace_root_path = package.path
                break  # Found the workspace root
            # Otherwise, track the shallowest package.json as potential root
            else:
                path_len = len(Path(package.path).parts)
                if path_len < shortest_path_len:
                    shortest_path_len = path_len
                    workspace_root_path = package.path
        except Exception:
            continue
    
    # Mark the workspace root
    if workspace_root_path:
        for package in packages:
            if package.path == workspace_root_path:
                # Create a new PackageJsonInfo with is_workspace_root=True
                package_info = PackageJsonInfo(
                    name=package.name,
                    path=package.path,
                    package_json_path=package.package_json_path,
                    main=package.main,
                    exports=package.exports,
                    dependencies=package.dependencies,
                    is_workspace_root=True
                )
                # Replace the package in the list
                packages[packages.index(package)] = package_info
                print(f"Marked workspace root: {package_info.name or 'unnamed'} at {package_info.path}")
                break

    print('workspace_root_path:', workspace_root_path)
    
    # Detect workspace metadata
    workspace_metadata = detect_workspace_metadata(repo_path)
    if workspace_metadata.type:
        print(f"Detected {workspace_metadata.type} workspace configuration")
    
    return packages, workspace_metadata