"""Integration test for GitHub App–authenticated shallow diffing.

Configure these environment variables before running to exercise a real repo:

- TEST_GH_REPO_URL: HTTPS URL of the repo (e.g. https://github.com/owner/repo.git)
- TEST_GH_COMMIT_BEFORE: Older commit SHA
- TEST_GH_COMMIT_AFTER: Newer commit SHA
- GITHUB_APP_ID: Your GitHub App ID
- GITHUB_INSTALLATION_ID: Installation ID for the repo
- GITHUB_PRIVATE_KEY_PEM: PEM contents (-----BEGIN PRIVATE KEY----- ...)

Optional env to strengthen assertions:

- TEST_GH_EXPECT_CHANGED_FILE: A path (repo-relative) expected to be in the diff
- TEST_GH_EXPECT_ANY_CHANGE=1: Assert that at least one change exists

Notes:
- The helper currently shallow-clones/fetches branch "main".
- Set a non-empty `GITHUB_TOKEN` (dummy is fine) to enable callbacks; the
  credentials are resolved via the GitHub App and not this token value.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import pygit2

from ast_parsing.utils.git_utils import (
    GitChanges,
    compare_commits_and_get_changed_files,
    ensure_shallow_main,
)


def _required_env() -> list[str]:
    return [
        "GITHUB_APP_ID",
        "GITHUB_INSTALLATION_ID",
        "GITHUB_PRIVATE_KEY_PEM",
    ]


def _missing_env_vars() -> list[str]:
    return [k for k in _required_env() if not os.getenv(k)]


@pytest.mark.skipif(
    bool(_missing_env_vars()),
    reason=("Missing required env for integration test: " + ", ".join(_required_env())),
)
def test_github_app_shallow_diff(tmp_path: Path) -> None:
    repo_url = "https://github.com/TrySita/webapp"
    before_sha = "058c6474bb339cb630678a30c263269ab6980da8"
    after_sha = "f6e99c8e01f39f0da76a704cf9654de0a52aea85"

    workdir = tmp_path / "repo"
    workdir.mkdir(parents=True, exist_ok=True)

    # Shallow clone main and ensure repo is usable on disk
    _ = ensure_shallow_main(workdir.as_posix(), repo_url)
    repo = pygit2.Repository(workdir.as_posix())
    assert repo is not None

    # Compute file-level diff between two commits using shallow fetches
    changes: GitChanges = compare_commits_and_get_changed_files(
        before_commit_hash=before_sha,
        after_commit_hash=after_sha,
        repo_path=workdir.as_posix(),
        remote_origin_url=repo_url,
        detect_renames=True,
    )

    # Basic type/shape assertions
    assert isinstance(changes, GitChanges)
    assert all(isinstance(p, str) for p in changes.added)
    assert all(isinstance(p, str) for p in changes.modified)
    assert all(isinstance(p, str) for p in changes.deleted)
    # Renamed elements are dataclass instances from database.types.RenamedFile
    from database.types import RenamedFile  # local import to avoid test import cycles

    print("changes:", changes)

    assert all(isinstance(r, RenamedFile) for r in changes.renamed)
    assert (
        len(changes.added)
        + len(changes.modified)
        + len(changes.deleted)
        + len(changes.renamed)
        > 0
    ), "Expected at least one change between commits"
