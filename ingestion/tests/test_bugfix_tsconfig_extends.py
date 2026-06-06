"""Regression tests for tsconfig ``extends`` resolution through node_modules.

Covers bug 8: monorepos that centralize tsconfig in a shared npm package
(e.g. ``@repo/typescript-config``) lost all path mappings because package
``extends`` targets were silently skipped instead of being resolved through
the cloned repo's ``node_modules``.
"""

import json
from pathlib import Path
from typing import Any

from ast_parsing.utils.ts_utils.tsconfig_parser import (
    extract_path_mappings,
    resolve_tsconfig_extends,
)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _build_shared_config_monorepo(root: Path) -> Path:
    """Create a Turborepo-style tree where the base tsconfig lives in a package.

    The shared base config (in node_modules) owns the path mappings; the
    consuming package only extends it. This mirrors the dominant Turborepo
    pattern where path mappings are centralized in ``@repo/typescript-config``.

    Returns the path to the consuming package's tsconfig.json.
    """
    # Shared config published as an npm package, available in node_modules.
    _write_json(
        root / "node_modules" / "@repo" / "typescript-config" / "base.json",
        {
            "compilerOptions": {
                "baseUrl": ".",
                "paths": {"@repo/ui": ["../../packages/ui/src"]},
            }
        },
    )

    # Consuming package extends the shared package config; it does not
    # redefine "paths" (TypeScript replaces the whole map when it does).
    app_tsconfig = root / "apps" / "web" / "tsconfig.json"
    _write_json(
        app_tsconfig,
        {
            "extends": "@repo/typescript-config/base.json",
            "compilerOptions": {"strict": True},
        },
    )
    return app_tsconfig


def test_package_extends_resolves_path_mappings_from_node_modules(
    tmp_path: Path,
) -> None:
    """Path mappings from a shared-config npm package must survive ``extends``."""
    app_tsconfig = _build_shared_config_monorepo(tmp_path)

    mappings = extract_path_mappings(str(app_tsconfig))

    # The inherited mapping from the shared package must be resolved, not dropped.
    assert "@repo/ui" in mappings


def test_package_extends_merges_compiler_options(tmp_path: Path) -> None:
    """resolve_tsconfig_extends must merge a package-extended config in."""
    app_tsconfig = _build_shared_config_monorepo(tmp_path)
    tsconfig_data: dict[str, Any] = json.loads(
        app_tsconfig.read_text(encoding="utf-8")
    )

    merged = resolve_tsconfig_extends(str(app_tsconfig), tsconfig_data)

    compiler_options = merged["compilerOptions"]
    assert "@repo/ui" in compiler_options["paths"]  # inherited from the package
    assert compiler_options["strict"] is True  # local option preserved


def test_missing_extends_package_is_handled_gracefully(tmp_path: Path) -> None:
    """A package ``extends`` with no matching node_modules entry must not raise."""
    app_tsconfig = tmp_path / "apps" / "web" / "tsconfig.json"
    _write_json(
        app_tsconfig,
        {
            "extends": "@repo/does-not-exist/base.json",
            "compilerOptions": {"paths": {"@/*": ["./src/*"]}},
        },
    )

    # Must not raise; the local config is still usable.
    mappings = extract_path_mappings(str(app_tsconfig))
    assert "@/*" in mappings
