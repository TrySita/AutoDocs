"""Git utilities for extracting repository information."""

from pygit2.credentials import UserPass

import os
from dataclasses import dataclass
from pygit2._pygit2 import Commit
from typing import Optional
from pygit2 import Repository
import pygit2
from pygit2.enums import DeltaStatus, DiffFind

from database.types import RenamedFile

from ..constants import EXTENSIONS
from .path_utils import get_file_extension


class GitHubAppAuth:
    """
    Minimal GitHub App auth for pygit2:
      - builds App JWT (10 min max)
      - exchanges for installation access token (~1 hour)
      - caches & refreshes token
      - provides a pygit2 credentials callback
    """

    def __init__(
        self,
        api_base: str = "https://api.github.com",
    ):
        self.api_base = api_base.rstrip("/")

    def remote_callbacks(self) -> pygit2.RemoteCallbacks:
        """Use in pygit2 clone/fetch: callbacks=auth.remote_callbacks()"""
        return pygit2.RemoteCallbacks(credentials=self._cred_cb())

    def _cred_cb(self) -> UserPass | None:
        """
        pygit2 credentials callback signature:
        return a Credentials object for HTTPS basic auth.
        For GitHub: username must be 'x-access-token', password is the installation token.
        """
        github_api_key = os.getenv("GITHUB_TOKEN")

        if not github_api_key:
            return None
        return pygit2.UserPass("x-access-token", github_api_key)


@dataclass
class GitChanges:
    """Represents the result of comparing two Git commits."""

    added: list[str]
    modified: list[str]
    deleted: list[str]
    renamed: list[RenamedFile]


@dataclass
class RepoInfo:
    remote_origin_url: str | None
    commit_hash: str | None
    default_branch: str | None


def extract_git_info(repo: Repository) -> RepoInfo:
    """
    Extract git repository information using pygit2.

    Args:
        repo_path: Path to the git repository

    Returns:
        Dictionary containing git repository information:
        - commit_hash: SHA hash of the current HEAD commit
        - default_branch: Name of the default/current branch
    """
    try:
        # Get latest commit info
        head_commit = repo.head.target

        # Get branch name
        default_branch = "main"  # fallback
        try:
            if not repo.head_is_detached:
                default_branch = repo.head.shorthand
        except Exception:
            pass  # Use fallback

        return RepoInfo(
            remote_origin_url=repo.remotes["origin"].url,
            commit_hash=str(head_commit),
            default_branch=default_branch,
        )

    except Exception as e:
        print(f"Warning: Could not extract git info from {repo.path}: {e}")
        return _fallback_git_info(repo.path)


def _fallback_git_info(repo_path: str) -> RepoInfo:
    """
    Fallback method to extract basic git info when pygit2 is unavailable.

    Args:
        repo_path: Path to the repository

    Returns:
        Basic repository information with None for git-specific fields
    """
    return RepoInfo(
        remote_origin_url=None,
        commit_hash=None,
        default_branch="main",
    )


def _auth_callbacks() -> Optional[pygit2.RemoteCallbacks]:
    app_auth = GitHubAppAuth()

    return app_auth.remote_callbacks()

def ensure_shallow_main(repo_path: str, remote_url: str) -> RepoInfo:
    """
    Ensure repo_path has origin/main checked out with depth=1.
    Creates the repo if needed, otherwise updates it shallowly.
    """
    is_existing_repo = os.path.isdir(repo_path) and os.path.isdir(
        os.path.join(repo_path, ".git")
    )

    if not is_existing_repo:
        # clone shallow on main
        repo = pygit2.clone_repository(
            url=remote_url,
            path=repo_path,
            callbacks=_auth_callbacks(),
            depth=1,  # shallow clone
        )
        return extract_git_info(repo)

    repo = pygit2.Repository(repo_path)
    # create origin if missing / fix URL if changed
    if "origin" not in [r.name for r in repo.remotes]:
        _ = repo.remotes.create("origin", remote_url)
    elif repo.remotes["origin"].url != remote_url:
        repo.remotes["origin"].url = remote_url  # pyright: ignore[reportAttributeAccessIssue]

    branch = repo.head.shorthand

    # fetch only main, shallow
    origin = repo.remotes["origin"]
    _ = origin.fetch(
        [f"+refs/heads/{branch}:refs/remotes/origin/{branch}"],
        callbacks=_auth_callbacks(),
        depth=1,
    )

    # fast-forward local main to remote main and checkout
    remote_ref = repo.lookup_reference(f"refs/remotes/origin/{branch}")
    target = remote_ref.target
    try:
        local_ref = repo.lookup_reference(f"refs/heads/{branch}")
        local_ref.set_target(target)
    except KeyError:
        _ = repo.create_reference(f"refs/heads/{branch}", target)

        # checkout updates files at HEAD (main)
    _ = repo.checkout(refname=f"refs/heads/{branch}")

    return extract_git_info(repo)


def ensure_commit_object(
    repo: pygit2.Repository,
    sha: str,
    remote_name: str = "origin",
) -> None:
    """
    Ensure the commit <sha> exists in the local object database.
    Keeps the working tree and HEAD as-is.
    """
    try:
        _ = repo.revparse_single(sha).peel(pygit2.Commit)
        return
    except Exception:
        pass

    if remote_name not in [r.name for r in repo.remotes]:
        raise ValueError(
            "Remote not configured; set origin before calling ensure_commit_object"
        )

    tmp_ref = f"refs/tmp/{sha}"
    refspec = f"+{sha}:{tmp_ref}"

    _ = repo.remotes[remote_name].fetch(
        [refspec],
        callbacks=_auth_callbacks(),
        depth=1,
    )

    try:
        repo.lookup_reference(tmp_ref).delete()
    except KeyError:
        pass

        # --- main function: file-level diff between two commits ---


def compare_commits_and_get_changed_files(
    before_commit_hash: str,
    after_commit_hash: str,
    repo_path: str,
    remote_origin_url: str | None = None,
    detect_renames: bool = True,  # turn off if you want zero extra blob work
) -> GitChanges:
    """
    Compute added/modified/deleted/renamed between two commits using pygit2.
    Only returns paths with extensions in EXTENSIONS.
    """
    repo = pygit2.Repository(repo_path)

    # wire up origin (if provided)
    if remote_origin_url and "origin" not in [r.name for r in repo.remotes]:
        repo.remotes.create("origin", remote_origin_url)

        # make sure both commits exist locally (no checkout needed)
    ensure_commit_object(
        repo,
        before_commit_hash,
    )
    ensure_commit_object(
        repo,
        after_commit_hash,
    )

    before: Commit = repo.revparse_single(before_commit_hash).peel(pygit2.Commit)
    after: Commit = repo.revparse_single(after_commit_hash).peel(pygit2.Commit)

    # tree-to-tree or commit-to-commit both work per docs; use commits directly
    diff = repo.diff(before, after)  # returns a Diff object
    # optional: detect renames/copies
    if detect_renames:
        diff.find_similar(
            flags=DiffFind.FIND_RENAMES | DiffFind.FIND_COPIES, rename_threshold=50
        )

    added, modified, deleted = [], [], []
    renamed: list[RenamedFile] = []

    for d in diff.deltas:  # iterate file-level changes
        oldp = d.old_file.path or ""
        newp = d.new_file.path or ""
        path_for_filter = newp or oldp
        if not path_for_filter or get_file_extension(path_for_filter) not in EXTENSIONS:
            continue

        st = d.status
        if st == DeltaStatus.ADDED:
            added.append(newp)
        elif st == DeltaStatus.MODIFIED:
            modified.append(newp)
        elif st == DeltaStatus.DELETED:
            deleted.append(oldp)
        elif st == DeltaStatus.RENAMED and detect_renames:
            # include if either side matches
            if (
                get_file_extension(oldp) in EXTENSIONS
                or get_file_extension(newp) in EXTENSIONS
            ):
                renamed.append(RenamedFile(old=oldp, new=newp))
        elif st == DeltaStatus.COPIED and detect_renames:
            added.append(newp)

    return GitChanges(added=added, modified=modified, deleted=deleted, renamed=renamed)
