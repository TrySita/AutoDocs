from typing import Any
from dataclasses import dataclass


@dataclass
class RenamedFile:
    """Represents a renamed file with old and new paths."""

    old: str
    new: str


class ParseDelta:
    """Summarizes the changes detected during a parse run.

    Designed to drive incremental DAG building and summary refreshes.
    """

    def __init__(
        self,
        files_added: list[str] | None = None,
        files_modified: list[str] | None = None,
        files_deleted: list[str] | None = None,
        files_renamed: list[RenamedFile] | None = None,
    ):
        # File-level changes (all paths are repository-relative)
        self.files_added: list[str] = files_added or []
        self.files_modified: list[str] = files_modified or []
        self.files_deleted: list[str] = files_deleted or []
        self.files_renamed: list[RenamedFile] = files_renamed or []

        # Definition-level changes (database IDs)
        self.definitions_added: set[int] = set()
        self.definitions_removed: set[int] = set()
        self.definitions_unchanged: set[int] = set()

        # Per-file mapping of definition deltas
        self.files_to_definitions: dict[str, "FileDefinitionDelta"] = {}

    def add_file_definition_delta(
        self,
        file_path: str,
        added_ids: set[int] | None = None,
        removed_ids: set[int] | None = None,
        unchanged_ids: set[int] | None = None,
    ) -> None:
        added: set[int] = set(added_ids or set())
        removed: set[int] = set(removed_ids or set())
        unchanged: set[int] = set(unchanged_ids or set())

        # Update global sets
        self.definitions_added.update(added)
        self.definitions_removed.update(removed)
        self.definitions_unchanged.update(unchanged)

        # Update per-file map
        self.files_to_definitions[file_path] = FileDefinitionDelta(
            added=added, removed=removed, unchanged=unchanged
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_added": self.files_added,
            "files_modified": self.files_modified,
            "files_deleted": self.files_deleted,
            "files_renamed": [(r.old, r.new) for r in self.files_renamed],
            "definitions_added": list(self.definitions_added),
            "definitions_removed": list(self.definitions_removed),
            "definitions_unchanged": list(self.definitions_unchanged),
            "files_to_definitions": {
                k: {
                    "added": list(v.added),
                    "removed": list(v.removed),
                    "unchanged": list(v.unchanged),
                }
                for k, v in self.files_to_definitions.items()
            },
        }


@dataclass
class FileDefinitionDelta:
    """Definition-level changes for a single file."""

    added: set[int]
    removed: set[int]
    unchanged: set[int]
