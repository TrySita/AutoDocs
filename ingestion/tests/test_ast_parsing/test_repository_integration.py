"""Test repository integration with AST parsing."""

import pytest
from database.manager import DatabaseManager, session_scope
from database.models import RepositoryModel, PackageModel, FileModel
from ast_parsing.parser import parse_and_persist_repo


class TestRepositoryIntegration:
    """Test repository information extraction and persistence."""

    @pytest.fixture
    def test_repo_path(self):
        """Placeholder for test repository path."""
        # TODO: Replace with actual test repository path
        return "/Users/sohan/Documents/trysita-onboard/analysis-agent-new/test-repos/merchie/"

    @pytest.fixture
    def expected_repo_info(self):
        """Expected repository information."""
        # TODO: Replace with actual expected values
        return {
            "remote_origin_url": "https://github.com/gadgetman6/merchie.git",
            "commit_hash": "00e666643a2d01dfd91dfd85f89cae6df0486741",
            "default_branch": "main",
        }

    @pytest.mark.asyncio
    async def test_repository_extraction_and_persistence(
        self, test_repo_path: str, expected_repo_info: dict, db_manager: DatabaseManager
    ):
        """Test that repository information is correctly extracted and persisted."""

        # Parse the repository
        await parse_and_persist_repo(test_repo_path, db_manager)

        with session_scope(db_manager) as session:
            # Verify repository was created with correct information
            repository = (
                session.query(RepositoryModel)
                .filter_by(remote_origin_url=expected_repo_info["remote_origin_url"])
                .first()
            )

            assert repository is not None, "Repository should be created"
            assert repository.commit_hash.startswith(
                expected_repo_info["commit_hash"][:12]
            )
            assert repository.default_branch == expected_repo_info["default_branch"]

            # Verify packages are linked to repository
            packages = (
                session.query(PackageModel).filter_by(repository_id=repository.id).all()
            )

            assert len(packages) > 0, "Should have at least one package"

            for package in packages:
                assert package.repository_id == repository.id
                assert package.repository == repository

            # Verify files can access repository through packages
            files = session.query(FileModel).all()
            assert len(files) > 0, "Should have parsed some files"

            # Test files that belong to packages in this repository
            files_with_packages = [f for f in files if f.package_id is not None]
            if files_with_packages:
                for file in files_with_packages:
                    # Test file -> package -> repository relationship chain
                    assert file.package is not None, (
                        "File should have package relationship"
                    )
                    assert file.package.repository == repository, (
                        "File's package should belong to repository"
                    )

            # Test that packages contain their files
            for package in packages:
                # Get files that belong to this package
                package_files = [f for f in files if f.package_id == package.id]
                # Test bidirectional relationship
                assert len(package.files) == len(package_files), (
                    "Package.files should match files with package_id"
                )
                for file in package.files:
                    assert file.package_id == package.id
                    assert file.package == package

    # @pytest.mark.asyncio
    # async def test_package_repository_relationship(
    #     self,
    #     test_repo_path: str,
    #     expected_repo_info: dict,
    #     db_manager: DatabaseManager
    # ):
    #     """Test that packages maintain proper relationship with repository."""

    #     await parse_and_persist_repo(test_repo_path, db_manager)

    #     with session_scope(db_manager) as session:
    #         repository = session.query(RepositoryModel).filter_by(
    #             name=expected_repo_info["name"]
    #         ).first()

    #         assert repository is not None

    #         # Test repository -> packages relationship
    #         packages = repository.packages
    #         assert len(packages) > 0, "Repository should have packages"

    #         # Test packages -> repository relationship
    #         for package in packages:
    #             assert package.repository == repository
    #             assert package.repository.name == expected_repo_info["name"]
    #             assert package.repository_id == repository.id
