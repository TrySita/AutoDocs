"""
TypeScript configuration parser for extracting path mappings.

This module provides functionality to parse tsconfig.json files and extract
path mapping configurations used for alias resolution.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def find_nearest_tsconfig(file_path: str) -> str | None:
    """
    Find the nearest tsconfig.json file by walking up the directory tree.

    Args:
        file_path: Starting file path to search from

    Returns:
        Path to nearest tsconfig.json file or None if not found
    """
    current_dir = (
        Path(file_path).parent if os.path.isfile(file_path) else Path(file_path)
    )

    while current_dir != current_dir.parent:  # Stop at filesystem root
        tsconfig_path = current_dir / "tsconfig.json"
        if tsconfig_path.exists():
            return str(tsconfig_path)
        current_dir = current_dir.parent

    return None


def parse_tsconfig_json(tsconfig_path: str) -> dict[str, Any] | None:
    """
    Parse a tsconfig.json file and return its contents.

    Args:
        tsconfig_path: Path to the tsconfig.json file

    Returns:
        Parsed tsconfig.json contents or None if parsing fails
    """
    try:
        with open(tsconfig_path, "r", encoding="utf-8") as f:
            content = f.read()

            # Remove comments from JSON content
            cleaned_content = _remove_json_comments(content)
            return json.loads(cleaned_content)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        logger.warning("Could not parse %s: %s", tsconfig_path, e)
        return None


def _remove_json_comments(content: str) -> str:
    """
    Remove both single-line (//) and multi-line (/* */) comments from JSON content.

    Args:
        content: Raw JSON content with comments

    Returns:
        JSON content with comments removed
    """
    result: list[str] = []
    i = 0
    in_string = False
    escape_next = False

    while i < len(content):
        char = content[i]

        if escape_next:
            result.append(char)
            escape_next = False
            i += 1
            continue

        if char == "\\" and in_string:
            result.append(char)
            escape_next = True
            i += 1
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            result.append(char)
            i += 1
            continue

        if in_string:
            result.append(char)
            i += 1
            continue

        # Handle comments outside of strings
        if char == "/" and i + 1 < len(content):
            next_char = content[i + 1]

            if next_char == "/":
                # Single-line comment - skip to end of line
                while i < len(content) and content[i] != "\n":
                    i += 1
                if i < len(content):
                    result.append("\n")  # Preserve the newline
                    i += 1
                continue

            elif next_char == "*":
                # Multi-line comment - skip to */
                i += 2  # Skip /*
                while i + 1 < len(content):
                    if content[i] == "*" and content[i + 1] == "/":
                        i += 2  # Skip */
                        break
                    i += 1
                continue

        result.append(char)
        i += 1

    return "".join(result)


def _split_extends_package(extends: str) -> tuple[str, str]:
    """Split a package ``extends`` target into its package name and subpath.

    Mirrors Node's module resolution: a scoped package keeps its first two
    segments (``@scope/name``) as the package name, an unscoped package keeps
    only the first. Everything after that is the subpath inside the package.

    Args:
        extends: The raw ``extends`` value, e.g. ``@repo/typescript-config/base.json``

    Returns:
        Tuple of (package_name, subpath); subpath is empty if none was given.
    """
    parts = extends.split("/")
    if extends.startswith("@"):
        package_name = "/".join(parts[:2])
        subpath = "/".join(parts[2:])
    else:
        package_name = parts[0]
        subpath = "/".join(parts[1:])
    return package_name, subpath


def _resolve_package_extends(tsconfig_dir: Path, extends: str) -> Path | None:
    """Resolve a package ``extends`` target through the cloned repo's node_modules.

    Walks up from the consuming tsconfig's directory to the filesystem root,
    looking for ``node_modules/<package>``, then resolves the requested file
    inside it (defaulting to ``tsconfig.json`` when no subpath is given, the
    way TypeScript does).

    Args:
        tsconfig_dir: Directory of the tsconfig.json that declares ``extends``
        extends: The package ``extends`` value (npm package, possibly scoped)

    Returns:
        Path to the extended config file, or None if no matching package file
        exists anywhere up the tree.
    """
    package_name, subpath = _split_extends_package(extends)
    relative_file = subpath if subpath else "tsconfig.json"

    current_dir = tsconfig_dir
    while True:
        package_dir = current_dir / "node_modules" / package_name
        if package_dir.is_dir():
            candidate = package_dir / relative_file
            if not candidate.suffix:
                candidate = candidate.with_suffix(".json")
            if candidate.exists():
                return candidate
        if current_dir == current_dir.parent:  # Reached filesystem root
            break
        current_dir = current_dir.parent

    return None


def resolve_tsconfig_extends(
    tsconfig_path: str, tsconfig_data: dict[str, Any], visited: set[str] | None = None
) -> dict[str, Any]:
    """
    Resolve tsconfig.json extends field and merge configurations.

    Args:
        tsconfig_path: Path to the current tsconfig.json file
        tsconfig_data: Parsed tsconfig.json data
        visited: Set of visited paths to prevent circular references

    Returns:
        Merged configuration with extended configs resolved
    """
    if visited is None:
        visited = set()

    # Normalize path to prevent circular references
    normalized_path = os.path.normpath(os.path.abspath(tsconfig_path))
    if normalized_path in visited:
        logger.warning(
            "Circular reference detected in tsconfig extends: %s", tsconfig_path
        )
        return tsconfig_data

    visited.add(normalized_path)

    extends = tsconfig_data.get("extends")
    if not isinstance(extends, str) or not extends:
        return tsconfig_data

    tsconfig_dir = Path(tsconfig_path).parent

    # TypeScript treats an extends target as a relative file only when it starts
    # with "./" or "../" (or is absolute); anything else is an npm package
    # resolved through node_modules (the dominant Turborepo shared-config
    # pattern, e.g. "@repo/typescript-config/base.json").
    if extends.startswith("./") or extends.startswith("../") or os.path.isabs(extends):
        extended_path = tsconfig_dir / extends
        if not extended_path.suffix:
            extended_path = extended_path.with_suffix(".json")
    else:
        resolved = _resolve_package_extends(tsconfig_dir, extends)
        if resolved is None:
            logger.warning(
                "Could not resolve package extends '%s' from %s via node_modules",
                extends,
                tsconfig_path,
            )
            return tsconfig_data
        extended_path = resolved

    if not extended_path.exists():
        return tsconfig_data

    extended_data = parse_tsconfig_json(str(extended_path))
    if not extended_data:
        return tsconfig_data

    # Recursively resolve extends in the extended config
    extended_data = resolve_tsconfig_extends(
        str(extended_path), extended_data, visited
    )

    # Merge configurations (current config overrides extended)
    merged = extended_data.copy()
    merged.update(tsconfig_data)

    # Merge compilerOptions separately
    if "compilerOptions" in extended_data and "compilerOptions" in tsconfig_data:
        merged["compilerOptions"] = {
            **extended_data["compilerOptions"],
            **tsconfig_data["compilerOptions"],
        }

    return merged


def resolve_tsconfig_references(
    tsconfig_path: str, tsconfig_data: dict[str, Any], visited: set[str] | None = None
) -> dict[str, list[str]]:
    """
    Resolve tsconfig.json references field and collect path mappings from referenced projects.

    Args:
        tsconfig_path: Path to the current tsconfig.json file
        tsconfig_data: Parsed tsconfig.json data
        visited: Set of already visited tsconfig paths to prevent circular references

    Returns:
        Dictionary of path mappings from all referenced projects
    """
    if visited is None:
        visited = set()

    # Prevent circular references
    resolved_tsconfig_path = str(Path(tsconfig_path).resolve())
    if resolved_tsconfig_path in visited:
        return {}

    visited.add(resolved_tsconfig_path)

    references = tsconfig_data.get("references")
    if not isinstance(references, list):
        return {}

    all_paths: dict[str, list[str]] = {}
    tsconfig_dir = Path(tsconfig_path).parent

    for ref in references:
        if not isinstance(ref, dict):
            continue

        ref_path = ref.get("path")
        if not isinstance(ref_path, str):
            continue

        # Resolve reference path relative to current tsconfig
        resolved_ref_path = tsconfig_dir / ref_path

        # If it's a directory, look for tsconfig.json in it
        if resolved_ref_path.is_dir():
            resolved_ref_path = resolved_ref_path / "tsconfig.json"
        elif not resolved_ref_path.suffix:
            resolved_ref_path = resolved_ref_path.with_suffix(".json")

        if resolved_ref_path.exists():
            # Parse referenced tsconfig
            ref_data = parse_tsconfig_json(str(resolved_ref_path))
            if ref_data:
                # Resolve extends in referenced config
                ref_data = resolve_tsconfig_extends(str(resolved_ref_path), ref_data)

                # Get path mappings from referenced config
                ref_paths = extract_path_mappings_direct(
                    str(resolved_ref_path), ref_data
                )

                # Merge path mappings (current config takes precedence)
                for pattern, paths in ref_paths.items():
                    if pattern not in all_paths:
                        all_paths[pattern] = paths

                # Recursively resolve references in the referenced config
                nested_paths = resolve_tsconfig_references(
                    str(resolved_ref_path), ref_data, visited.copy()
                )
                for pattern, paths in nested_paths.items():
                    if pattern not in all_paths:
                        all_paths[pattern] = paths

    return all_paths


def extract_path_mappings_direct(
    tsconfig_path: str, tsconfig_data: dict[str, Any]
) -> dict[str, list[str]]:
    """
    Extract path mappings directly from parsed tsconfig data.

    Args:
        tsconfig_path: Path to the tsconfig.json file
        tsconfig_data: Parsed tsconfig.json data

    Returns:
        Dictionary mapping path patterns to their resolved paths
    """
    compiler_options_raw = tsconfig_data.get("compilerOptions")
    if not isinstance(compiler_options_raw, dict):
        return {}

    # Cast to proper type since we've verified it's a dict
    compiler_options: dict[str, Any] = compiler_options_raw

    paths_raw = compiler_options.get("paths")
    if not isinstance(paths_raw, dict):
        return {}

    # Cast to proper type since we've verified it's a dict
    paths: dict[str, Any] = paths_raw

    base_url_raw = compiler_options.get("baseUrl", ".")
    base_url = "." if not isinstance(base_url_raw, str) else base_url_raw

    # Resolve paths relative to the tsconfig.json location and baseUrl
    tsconfig_dir = Path(tsconfig_path).parent
    base_dir = tsconfig_dir / base_url

    resolved_paths: dict[str, list[str]] = {}
    for pattern_raw, path_list_raw in paths.items():
        if not isinstance(pattern_raw, str) or not isinstance(path_list_raw, list):
            continue

        pattern: str = pattern_raw
        resolved_list: list[str] = []

        for path_raw in path_list_raw:
            if isinstance(path_raw, str):
                # Resolve relative to baseUrl
                resolved_path = (base_dir / path_raw).resolve()
                resolved_list.append(str(resolved_path))

        if resolved_list:  # Only add if we have valid paths
            resolved_paths[pattern] = resolved_list

    return resolved_paths


def extract_path_mappings(tsconfig_path: str) -> dict[str, list[str]]:
    """
    Extract path mappings from a tsconfig.json file, including from referenced projects.

    Args:
        tsconfig_path: Path to the tsconfig.json file

    Returns:
        Dictionary mapping path patterns to their resolved paths
    """
    tsconfig_data = parse_tsconfig_json(tsconfig_path)
    if not tsconfig_data:
        return {}

    # Resolve extends if present
    tsconfig_data = resolve_tsconfig_extends(tsconfig_path, tsconfig_data)

    # Get path mappings from the current config
    current_paths = extract_path_mappings_direct(tsconfig_path, tsconfig_data)

    # Get path mappings from referenced projects
    referenced_paths = resolve_tsconfig_references(tsconfig_path, tsconfig_data)

    # Merge path mappings (current config takes precedence over references)
    all_paths = referenced_paths.copy()
    all_paths.update(current_paths)

    return all_paths


def get_path_mappings_for_file(file_path: str) -> dict[str, list[str]]:
    """
    Get path mappings for a specific file by finding its nearest tsconfig.json.

    Args:
        file_path: Path to the file

    Returns:
        Dictionary of path mappings applicable to the file
    """
    tsconfig_path = find_nearest_tsconfig(file_path)
    if not tsconfig_path:
        return {}

    return extract_path_mappings(tsconfig_path)
