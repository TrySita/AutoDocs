"""Tests for monorepo configuration detection and setup in PackageRegistry."""

# Add src to path to avoid circular import issues

from ast_parsing.utils.package_registry import PackageRegistry


class TestMonorepoConfigurations:
    """Test monorepo configuration detection and setup."""

    def test_pnpm_workspace_detection(self):
        """Test that pnpm workspaces are correctly detected and configured."""
        # Use the test repository we created
        test_repo_path = "/Users/sohan/Documents/trysita-onboard/analysis-agent-new/tests/typescript-repos/pnpm-workspace-repo"

        # Initialize PackageRegistry
        registry = PackageRegistry(test_repo_path)

        # Verify workspace metadata is detected
        assert registry.workspace_metadata is not None
        assert registry.workspace_metadata.type == "pnpm"
        assert "packages/*" in registry.workspace_metadata.patterns

        # Verify monorepo setup info
        assert registry.monorepo_setup_info is not None
        assert registry.monorepo_setup_info.type == "managed_workspace"
        assert registry.monorepo_setup_info.workspace_manager == "pnpm"
        assert not registry.monorepo_setup_info.synthetic_tsconfig_created
        assert not registry.monorepo_setup_info.symlinks_created
        assert not registry.monorepo_setup_info.tsconfig_extended

        # Verify packages are discovered
        all_packages = registry.get_all_packages()
        assert len(all_packages) == 3  # root + ui + utils

        # Verify workspace root
        workspace_root = registry.get_workspace_root()
        assert workspace_root is not None
        assert workspace_root.name == "pnpm-workspace-root"
        assert workspace_root.is_workspace_root

        # Verify workspace packages
        workspace_packages = registry.get_workspace_packages()
        assert len(workspace_packages) == 2  # ui + utils

        package_names = {pkg.name for pkg in workspace_packages}
        assert "@workspace/ui" in package_names
        assert "@workspace/utils" in package_names

        # Verify cross-package dependencies
        utils_package = registry.get_package("@workspace/utils")
        assert utils_package is not None
        assert "@workspace/ui" in utils_package.dependencies

        # Verify entry points are resolved
        ui_package = registry.get_package("@workspace/ui")
        assert ui_package is not None
        assert ui_package.entry_point is not None
        assert ui_package.entry_point.endswith("src/index.ts")

    def test_yarn_workspace_detection(self):
        """Test that yarn workspaces are correctly detected and configured."""
        test_repo_path = "/Users/sohan/Documents/trysita-onboard/analysis-agent-new/tests/typescript-repos/yarn-workspace-repo"

        registry = PackageRegistry(test_repo_path)

        # Verify workspace metadata is detected
        assert registry.workspace_metadata is not None
        assert registry.workspace_metadata.type == "yarn"
        assert "apps/*" in registry.workspace_metadata.patterns
        assert "libs/*" in registry.workspace_metadata.patterns

        # Verify monorepo setup info
        assert registry.monorepo_setup_info is not None
        assert registry.monorepo_setup_info.type == "managed_workspace"
        assert registry.monorepo_setup_info.workspace_manager == "yarn"

        # Verify packages are discovered
        all_packages = registry.get_all_packages()
        assert len(all_packages) == 3  # root + web + shared

        # Verify workspace root
        workspace_root = registry.get_workspace_root()
        assert workspace_root is not None
        assert workspace_root.name == "yarn-workspace-root"

        # Verify workspace packages
        workspace_packages = registry.get_workspace_packages()
        assert len(workspace_packages) == 2  # web + shared

        package_names = {pkg.name for pkg in workspace_packages}
        assert "@company/web" in package_names
        assert "@company/shared" in package_names

        # Verify cross-package dependencies
        web_package = registry.get_package("@company/web")
        assert web_package is not None
        assert "@company/shared" in web_package.dependencies

    def test_direct_imports_monorepo(self):
        """Test that direct import monorepos are correctly detected and configured."""
        test_repo_path = "/Users/sohan/Documents/trysita-onboard/analysis-agent-new/tests/typescript-repos/direct-imports-repo"

        # Store original tsconfig for cleanup
        import json
        import os

        tsconfig_path = os.path.join(test_repo_path, "tsconfig.json")
        original_tsconfig = None
        if os.path.exists(tsconfig_path):
            with open(tsconfig_path, "r") as f:
                original_tsconfig = json.load(f)

        registry = PackageRegistry(test_repo_path)

        # Verify workspace metadata (should be None - no workspace configuration)
        assert registry.workspace_metadata is not None
        assert registry.workspace_metadata.type is None

        # Verify monorepo setup info
        assert registry.monorepo_setup_info is not None
        assert registry.monorepo_setup_info.type == "direct_import_monorepo"
        assert registry.monorepo_setup_info.workspace_manager is None
        assert not registry.monorepo_setup_info.synthetic_tsconfig_created
        assert not registry.monorepo_setup_info.symlinks_created
        assert registry.monorepo_setup_info.tsconfig_extended

        # Verify packages are discovered
        all_packages = registry.get_all_packages()
        assert len(all_packages) == 3  # root + core + api

        # Verify root package exists but is workspace root
        workspace_root = registry.get_workspace_root()
        assert workspace_root is not None
        assert workspace_root.name == "direct-imports-monorepo"

        # Verify packages
        workspace_packages = registry.get_workspace_packages()
        assert len(workspace_packages) == 2  # core + api

        package_names = {pkg.name for pkg in workspace_packages}
        assert "core" in package_names
        assert "api" in package_names

        # Verify tsconfig.json was extended with references
        assert os.path.exists(tsconfig_path)

        with open(tsconfig_path, "r") as f:
            tsconfig = json.load(f)

        assert "references" in tsconfig
        references = tsconfig["references"]
        reference_paths = {ref["path"] for ref in references}
        assert "core" in reference_paths
        assert "api" in reference_paths

        # Cleanup: Restore original tsconfig
        if original_tsconfig is not None:
            with open(tsconfig_path, "w") as f:
                json.dump(original_tsconfig, f, indent=2)
        else:
            os.remove(tsconfig_path)

    def test_package_based_monorepo(self):
        """Test that package-based monorepos are correctly detected and configured."""
        test_repo_path = "/Users/sohan/Documents/trysita-onboard/analysis-agent-new/tests/typescript-repos/package-based-repo"

        # Store original tsconfig for cleanup
        import json
        import os
        import shutil

        tsconfig_path = os.path.join(test_repo_path, "tsconfig.json")
        node_modules_path = os.path.join(test_repo_path, "node_modules")
        original_tsconfig = None
        if os.path.exists(tsconfig_path):
            with open(tsconfig_path, "r") as f:
                original_tsconfig = json.load(f)

        registry = PackageRegistry(test_repo_path)

        # Verify workspace metadata (should be None - no workspace configuration)
        assert registry.workspace_metadata is not None
        assert registry.workspace_metadata.type is None

        # Verify monorepo setup info
        assert registry.monorepo_setup_info is not None
        assert registry.monorepo_setup_info.type == "package_based_monorepo"
        assert registry.monorepo_setup_info.workspace_manager is None
        assert registry.monorepo_setup_info.synthetic_tsconfig_created
        assert registry.monorepo_setup_info.symlinks_created
        assert not registry.monorepo_setup_info.tsconfig_extended

        # Verify packages are discovered
        all_packages = registry.get_all_packages()
        assert len(all_packages) == 3  # root + auth-lib + user-service

        # Verify root package exists and is workspace root
        workspace_root = registry.get_workspace_root()
        assert workspace_root is not None
        assert workspace_root.name == "package-based-monorepo"

        # Verify packages
        workspace_packages = registry.get_workspace_packages()
        assert len(workspace_packages) == 2  # auth-lib + user-service

        package_names = {pkg.name for pkg in workspace_packages}
        assert "auth-lib" in package_names
        assert "user-service" in package_names

        # Verify cross-package dependencies (user-service depends on auth-lib)
        user_service = registry.get_package("user-service")
        assert user_service is not None
        assert "auth-lib" in user_service.dependencies

        # Verify synthetic tsconfig.json was created at root
        assert os.path.exists(tsconfig_path)

        with open(tsconfig_path, "r") as f:
            tsconfig = json.load(f)

        assert "references" in tsconfig
        references = tsconfig["references"]
        reference_paths = {ref["path"] for ref in references}
        assert "auth-lib" in reference_paths
        assert "user-service" in reference_paths

        # Verify symlinks were created in node_modules
        assert os.path.exists(node_modules_path)

        auth_lib_symlink = os.path.join(node_modules_path, "auth-lib")
        user_service_symlink = os.path.join(node_modules_path, "user-service")

        # Check if symlinks exist and point to correct paths
        assert os.path.islink(auth_lib_symlink) or os.path.isdir(auth_lib_symlink)
        assert os.path.islink(user_service_symlink) or os.path.isdir(
            user_service_symlink
        )

        if os.path.islink(auth_lib_symlink):
            expected_target = os.path.join(test_repo_path, "auth-lib")
            actual_target = os.readlink(auth_lib_symlink)
            assert os.path.samefile(actual_target, expected_target)

        if os.path.islink(user_service_symlink):
            expected_target = os.path.join(test_repo_path, "user-service")
            actual_target = os.readlink(user_service_symlink)
            assert os.path.samefile(actual_target, expected_target)

        # Cleanup: Restore original state
        if original_tsconfig is not None:
            with open(tsconfig_path, "w") as f:
                json.dump(original_tsconfig, f, indent=2)
        else:
            if os.path.exists(tsconfig_path):
                os.remove(tsconfig_path)

        if os.path.exists(node_modules_path):
            shutil.rmtree(node_modules_path)
