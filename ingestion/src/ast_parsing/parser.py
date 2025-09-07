"""
Main parser implementation for AST parsing.

This is the core parsing engine that handles:
- Single file parsing: parseFile()
- Directory parsing: recursiveParseDirectory()
- File-to-JSON conversion: parseFileToJSON()
- Definition categorization: getDefinitionKind()
"""

import logging
from sqlalchemy.orm import Session
from collections import defaultdict
import os
import asyncio
from typing import Any
from tree_sitter import Node, QueryCursor

from ast_parsing.utils.ts_utils.package_registry import PackageRegistry
from database.manager import DatabaseManager, get_current_session, session_scope
from database.models import (
    DefinitionModel,
    FileModel,
    ImportModel,
    PackageModel,
    RepositoryModel,
)
from database.types import ParseDelta

from .utils.db_utils import (
    hash_source_code,
    strip_comments,
)

from .types import (
    ParsedASTResult,
    FileParseResult,
    UnpersistedParseResult,
)
from .language_parser import load_required_language_parsers, LanguageParserInfo
from .file_discovery import list_files
from .utils.fs_utils import file_exists_at_path
from .utils.path_utils import (
    get_file_extension,
    get_repo_path,
    resolve_path,
    as_relative_path,
)
from .utils.language_helpers import (
    get_language_name,
)
from .utils.git_utils import (
    compare_commits_and_get_changed_files,
    GitChanges,
)
from .utils.path_utils import get_repo_path

from .constants import EXTENSIONS, KINDS

logger = logging.getLogger(__name__)


def extract_capture_node(
    captures: dict[str, list[Node]], capture_name: str, index: int = 0
) -> Node | None:
    """
    Efficiently extract a single node from QueryCursor captures.

    Args:
        captures: Dictionary from QueryCursor.matches() where keys are capture names
                 and values are lists of nodes
        capture_name: Name of the capture to extract
        index: Index of the node to extract from the list (default: 0)

    Returns:
        The node at the specified index, or None if not found
    """
    nodes = captures.get(capture_name, [])
    return nodes[index] if len(nodes) > index else None


def pick(nodes: dict[str, list[Node]], *keys: str):
    for k in keys:
        n = extract_capture_node(nodes, k)
        if n is not None:
            return n
    return None


def extract_capture_text(
    captures: dict[str, list[Node]],
    capture_name: str,
    index: int = 0,
    strip_quotes: bool = False,
) -> str | None:
    """
    Efficiently extract text from a capture node.

    Args:
        captures: Dictionary from QueryCursor.matches()
        capture_name: Name of the capture to extract
        index: Index of the node to extract from the list (default: 0)
        strip_quotes: Whether to strip surrounding quotes (default: False)

    Returns:
        The decoded text, or None if not found
    """
    node = extract_capture_node(captures, capture_name, index)
    if not node or not node.text:
        return None

    text = node.text.decode("utf-8")
    if strip_quotes:
        text = text.strip("'\"")
    return text


class ASTParser:
    """
    Main AST parser for extracting code structure and dependencies.

    This class handles the complete parsing pipeline from files to structured data.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        repository: RepositoryModel | None = None,
    ):
        self.parsed_files: dict[str, FileParseResult] = {}
        self.all_files: list[str] = []
        self.files_to_parse: list[str] = []
        self.remaining_files: list[str] = []
        self.external_dependencies: dict[str, Any] = {}  # pyright: ignore[reportExplicitAny]
        self.repo_path: str = ""
        self.db_manager: DatabaseManager = db_manager
        self.package_registry: PackageRegistry | None = None
        self.repository: RepositoryModel | None = repository
        self.current_delta: ParseDelta | None = None

    async def recursive_parse_directory(
        self,
        dir_path: str,
        new_commit_hash: str | None = None,
    ) -> ParsedASTResult:
        """
        Recursively parse all files in a directory and return structured results.

        Args:
            dir_path: Directory path to parse

        Returns:
            ParsedASTResult object with complete parsing results

        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        print(f"Starting recursive parsing of directory: {dir_path}")

        self.repo_path = dir_path

        should_do_incremental = False
        session = get_current_session()

        if self.repository and self.repository.commit_hash and new_commit_hash:
            print(
                f"Processing repository: {self.repository.remote_origin_url} (commit: {self.repository.commit_hash})"
            )

            if new_commit_hash != self.repository.commit_hash:
                print(
                    f"Incremental parsing: comparing {self.repository.commit_hash[:8]}...{new_commit_hash[:8]}"
                )
                should_do_incremental = True
            else:
                print("No changes detected, repository is up to date")
                # Early return - no parsing needed
                return ParsedASTResult(
                    directory_path=dir_path,
                    total_files=0,
                    parsed_files=0,
                    unparsed_files=0,
                    unparsed_files_list=[],
                )
        else:
            print("Full parsing: new repository")

        # Check if the path exists
        resolved_path: str = resolve_path(path_str=dir_path)
        if not await file_exists_at_path(file_path=resolved_path):
            raise FileNotFoundError(f"Directory does not exist: {dir_path}")

        # Initialize package registry and alias resolver
        self.package_registry = PackageRegistry(self.repo_path)

        # Print package discovery summary
        self.package_registry.print_summary()

        # Persist packages to database
        self._persist_packages_to_database()

        logger.info(f"Should do incremental parsing: {should_do_incremental}")

        # Determine which files to process based on parsing mode
        if (
            should_do_incremental
            and self.repository
            and self.repository.commit_hash
            and new_commit_hash
        ):
            # Initialize change delta for this run
            self.current_delta = ParseDelta()

            # Get changed files from git diff
            git_changes = compare_commits_and_get_changed_files(
                before_commit_hash=self.repository.commit_hash,
                after_commit_hash=new_commit_hash,
                repo_path=resolved_path,
                remote_origin_url=self.repository.remote_origin_url,
            )

            # Convert relative paths to absolute paths for processing
            changed_files: list[str] = []
            for file_path in git_changes.added + git_changes.modified:
                abs_path = os.path.join(resolved_path, file_path)
                if os.path.exists(abs_path):
                    changed_files.append(abs_path)

            self.all_files = changed_files
            print(f"Found {len(self.all_files)} changed files to process")

            self.current_delta.files_added.extend(git_changes.added)
            self.current_delta.files_modified.extend(git_changes.modified)

            # Handle deletions and renames before processing new files
            await self._handle_file_deletions_and_renames(git_changes, dir_path)
        else:
            # Full parsing: get all files recursively
            self.all_files = await list_files(resolved_path, recursive=True)
            print(f"Found {len(self.all_files)} files to process")

        # Separate files to parse and remaining files
        self._separate_files(all_files=self.all_files)

        # Initialize result structure
        result = ParsedASTResult(
            directory_path=dir_path,
            total_files=len(self.files_to_parse) + len(self.remaining_files),
            parsed_files=len(self.files_to_parse),
            unparsed_files=len(self.remaining_files),
            unparsed_files_list=[
                as_relative_path(file_path=f) for f in self.remaining_files
            ],
        )

        if self.files_to_parse:
            # Load language parsers for all files
            language_parsers = await self._load_parsers(files=self.files_to_parse)

            # Parse each file
            for i, file_path in enumerate(self.files_to_parse):
                # Use the resolved absolute repo root to compute stable relative paths
                relative_path = get_repo_path(file_path, repo_path=resolved_path)
                print(
                    f"Parsing file {i + 1}/{len(self.files_to_parse)}: {relative_path}"
                )
                try:
                    ext = get_file_extension(file_path)
                    language = get_language_name(ext)

                    with open(file_path, "r", encoding="utf-8") as f:
                        file_content = f.read()

                    parser_info = language_parsers.get(ext)
                    if not parser_info:
                        raise ValueError(
                            f"No parser available for extension {ext} in file {file_path}"
                        )

                    # Determine which package this file belongs to
                    package_model: PackageModel | None = None
                    if self.package_registry:
                        package_for_file = (
                            self.package_registry.get_package_containing_file(file_path)
                        )
                        if package_for_file:
                            # Find the package model ID in database
                            relative_package_path = (
                                self.package_registry.get_relative_path(
                                    package_for_file.path
                                )
                            )
                            package_model = (
                                session.query(PackageModel)
                                .filter_by(path=relative_package_path)
                                .first()
                            )

                    file_result = self._process_file_with_comparison(
                        file_path=file_path,
                        relative_path=relative_path,
                        file_content=file_content,
                        language=language,
                        parser_info=parser_info,
                        package_model=package_model,
                        session=session,
                        should_do_incremental=should_do_incremental,
                    )
                    result.files[relative_path] = file_result

                    # Aggregate dependencies
                    result.dependencies["imports"].extend(  # pyright: ignore[reportAny]
                        [imp.__dict__ for imp in file_result.imports]
                    )
                    result.dependencies["exports"].extend(file_result.exports)  # pyright: ignore[reportAny]

                except Exception as e:
                    print(f"Warning: Error parsing file {file_path}: {e}")
                    continue

        return result

    def _persist_packages_to_database(self):
        """Persist discovered packages to the database."""

        print(f'package registry: {self.package_registry}')
        print(f'repository: {self.repository}')

        if not self.package_registry or not self.repository:
            return

        session = get_current_session()

        for package_info in self.package_registry.get_all_packages():
            # Convert absolute path to relative path
            relative_path = self.package_registry.get_relative_path(package_info.path)
            relative_entry_point = None
            if package_info.entry_point:
                relative_entry_point = self.package_registry.get_relative_path(
                    package_info.entry_point
                )

            print(f"Persisting package: {package_info.name} at {relative_path}")

            package_model = PackageModel(
                repository=self.repository,
                name=package_info.name
                or f"unnamed-{os.path.basename(package_info.path)}",
                path=relative_path,
                entry_point=relative_entry_point,
                is_workspace_root=package_info.is_workspace_root,
                workspace_type=self.package_registry.workspace_metadata.type
                if self.package_registry.workspace_metadata
                else None,
            )
            session.add(package_model)

            print(
                f"Persisted {len(self.package_registry.get_all_packages())} packages to database"
            )

    async def _handle_file_deletions_and_renames(
        self, git_changes: GitChanges, repo_path: str
    ) -> None:
        """
        Handle file deletions and renames in the database during incremental parsing.

        Args:
            git_changes: GitChanges object with added/modified/deleted/renamed files
            repo_path: Repository root path
        """

        with session_scope(self.db_manager) as session:
            # Handle deleted files - remove from database
            for deleted_file in git_changes.deleted:
                relative_path = get_repo_path(deleted_file, repo_path=repo_path)
                file_record = (
                    session.query(FileModel).filter_by(file_path=relative_path).first()
                )
                if file_record:
                    print(f"Removing deleted file from database: {relative_path}")
                    session.delete(file_record)
                # Record in delta
                if self.current_delta is not None:
                    self.current_delta.files_deleted.append(relative_path)

            # Handle renamed files - update file paths in database
            for renamed_file in git_changes.renamed:
                old_relative_path = get_repo_path(renamed_file.old, repo_path=repo_path)
                new_relative_path = get_repo_path(renamed_file.new, repo_path=repo_path)

                file_record = (
                    session.query(FileModel)
                    .filter_by(file_path=old_relative_path)
                    .first()
                )
                if file_record:
                    print(
                        f"Updating renamed file: {old_relative_path} -> {new_relative_path}"
                    )
                    file_record.file_path = new_relative_path

                # Record in delta
                if self.current_delta is not None:
                    self.current_delta.files_renamed.append(
                        type(renamed_file)(old=old_relative_path, new=new_relative_path)
                    )

            session.commit()

    def _process_file_with_comparison(
        self,
        file_path: str,
        relative_path: str,
        file_content: str,
        language: str,
        parser_info: LanguageParserInfo,
        package_model: PackageModel | None,
        session: Session,
        should_do_incremental: bool,
    ) -> FileParseResult:
        """
        Process a file with smart comparison for incremental parsing.

        Returns:
            FileParseResult with the final processing results
        """
        # Parse the file without persistence first
        unpersisted_result: UnpersistedParseResult = self._parse_file_to_json(
            file_path=file_path,
            file_content=file_content,
            language=language,
            parser_info=parser_info,
        )

        if should_do_incremental:
            # Check if file already exists in database
            existing_file = (
                session.query(FileModel).filter_by(file_path=relative_path).first()
            )

            if existing_file:
                # Get existing definitions for comparison
                existing_definitions = (
                    session.query(DefinitionModel).filter_by(file=existing_file).all()
                )
                existing_def_hashes = {
                    d.source_code_hash: d for d in existing_definitions
                }
                new_def_hashes = {
                    d.source_code_hash: d for d in unpersisted_result.definitions
                }

                # Find changes
                removed_hashes = set(existing_def_hashes.keys()) - set(
                    new_def_hashes.keys()
                )
                added_hashes = set(new_def_hashes.keys()) - set(
                    existing_def_hashes.keys()
                )
                unchanged_hashes = set(existing_def_hashes.keys()) & set(
                    new_def_hashes.keys()
                )

                print(f"  Comparison for {relative_path}:")
                print(f"    - {len(removed_hashes)} definitions removed")
                print(f"    - {len(added_hashes)} definitions added")
                print(f"    - {len(unchanged_hashes)} definitions unchanged")

                # Remove deleted definitions and their dependencies
                removed_ids: set[int] = set()
                for hash_val in removed_hashes:
                    definition = existing_def_hashes[hash_val]
                    print(f"    Removing definition: {definition.name}")
                    if definition.id is not None:
                        removed_ids.add(definition.id)
                    session.delete(definition)

                # Update file content
                existing_file.file_content = file_content.strip()

                # Remove old imports and add new ones
                old_imports = (
                    session.query(ImportModel).filter_by(file=existing_file).all()
                )
                for old_import in old_imports:
                    session.delete(old_import)

                # Add new imports
                for import_model in unpersisted_result.imports:
                    import_model.file = existing_file
                    session.add(import_model)

                session.flush()  # flush so new definitions don't conflict

                # Add new definitions
                final_definitions: list[DefinitionModel] = []
                for hash_val in added_hashes:
                    new_definition: DefinitionModel = new_def_hashes[hash_val]
                    new_definition.file = existing_file
                    session.add(new_definition)
                    final_definitions.append(new_definition)

                # Keep unchanged definitions
                final_definitions.extend(
                    [existing_def_hashes[h] for h in unchanged_hashes]
                )

                session.flush()

                # Update delta with per-file definition changes
                if self.current_delta is not None:
                    added_ids: set[int] = {
                        d.id
                        for h, d in new_def_hashes.items()
                        if h in added_hashes and d.id is not None
                    }
                    unchanged_ids: set[int] = {
                        existing_def_hashes[h].id
                        for h in unchanged_hashes
                        if existing_def_hashes[h].id is not None
                    }
                    self.current_delta.add_file_definition_delta(
                        file_path=relative_path,
                        added_ids=added_ids,
                        removed_ids=removed_ids,
                        unchanged_ids=unchanged_ids,
                    )

                return FileParseResult(
                    language=language,
                    definitions=final_definitions,
                    imports=unpersisted_result.imports,
                    exports=unpersisted_result.exports,
                )

        # New file or full parsing - create and persist everything
        file_model = FileModel(
            package=package_model,
            file_path=relative_path,
            language=language,
            file_content=file_content.strip(),
        )
        session.add(file_model)
        session.flush()

        # Associate models with the file and add to session
        for definition in unpersisted_result.definitions:
            definition.file = file_model
            session.add(definition)

        session.flush()

        # In full/new file case, record all definitions as added
        if self.current_delta is not None:
            added_ids: set[int] = {
                d.id for d in unpersisted_result.definitions if d.id is not None
            }
            self.current_delta.add_file_definition_delta(
                file_path=relative_path,
                added_ids=added_ids,
                removed_ids=set(),
                unchanged_ids=set(),
            )

        return FileParseResult(
            language=language,
            definitions=unpersisted_result.definitions,
            imports=unpersisted_result.imports,
            exports=unpersisted_result.exports,
        )

    def _separate_files(self, all_files: list[str]) -> None:
        """
        Separate files into parseable and non-parseable categories.

        Args:
            all_files: List of all file paths
        """
        files_to_parse: list[str] = []
        remaining_files: list[str] = []

        for file in all_files:
            ext: str = get_file_extension(file_path=file)
            if ext in EXTENSIONS:
                files_to_parse.append(file)
            elif not os.path.isdir(s=file):
                remaining_files.append(file)

        self.files_to_parse = files_to_parse
        self.remaining_files = remaining_files

    def _parse_file_to_json(
        self,
        file_path: str,
        file_content: str,
        language: str,
        parser_info: LanguageParserInfo,
    ) -> UnpersistedParseResult:
        """
        Parse file and return unpersisted structure with dependencies.

        Args:
            file_path: Path to file to parse
            file_content: File content to parse
            ext: File extension
            language: Programming language
            parser_info: Parser information

        Returns:
            UnpersistedParseResult object
        """

        definitions: list[DefinitionModel] = []
        tree_imports: list[ImportModel] = []
        tree_exports: list[tuple[str, str]] = []  # tuple of name, source code

        try:
            # Parse the file content into an Abstract Syntax Tree (AST)
            tree = parser_info.parser.parse(bytes(file_content, "utf-8"))
            seen_full: defaultdict[int, bool] = defaultdict(
                bool
            )  # Track seen definitions
            seen_start: defaultdict[int, bool] = defaultdict(
                bool
            )  # Track seen start lines

            # Apply the query to get definitions, imports, and exports
            cursor = QueryCursor(parser_info.query)

            ### Process definitions ###
            for _, captures in cursor.matches(tree.root_node):
                kind = None
                def_node = None
                name_node = None

                for k in KINDS:
                    def_node = pick(captures, f"def_{k}")
                    if def_node:
                        name_node = pick(captures, f"name_{k}", "name")  # fallback
                        kind = k
                        break

                if not def_node or not def_node.text:
                    continue

                def_name = (
                    name_node.text.decode("utf-8").strip()
                    if name_node and name_node.text
                    else "anonymous"
                )

                # Check if anonymous or variable definitions have already been seen, we don't care about them
                if def_name == "anonymous" or kind == "variable":
                    if seen_full.get(def_node.start_point[0] + 1, False):
                        continue

                if seen_start.get(
                    def_node.start_point[0] + 1, False
                ):  # If the start line is repeated, we skip
                    continue
                else:
                    for line in range(
                        def_node.start_point[0] + 1,
                        def_node.end_point[0] + 1,
                    ):
                        seen_full[line] = True
                    seen_start[def_node.start_point[0] + 1] = True

                definition_source_code = def_node.text.decode("utf-8").strip()

                is_default_export = False

                definition = DefinitionModel(
                    name=def_name,
                    start_line=def_node.start_point[0] + 1,  # 1-based
                    end_line=def_node.end_point[0] + 1,
                    source_code=definition_source_code,
                    source_code_hash=hash_source_code(
                        def_name=def_name,
                        source_code_cleaned=strip_comments(
                            language=language, source_code=definition_source_code
                        ),
                    ),
                    definition_type=kind or "unknown",
                    docstring=extract_capture_text(captures, "doc"),
                    is_default_export=is_default_export,
                )

                definitions.append(definition)

        except Exception as error:
            print(f"Error parsing file {file_path}: {error}")
            raise

        return UnpersistedParseResult(
            definitions=definitions,
            imports=tree_imports,
            exports=tree_exports,
        )

    async def _load_parsers(self, files: list[str]) -> dict[str, LanguageParserInfo]:
        """Load language parsers asynchronously."""
        return await asyncio.get_event_loop().run_in_executor(
            None, load_required_language_parsers, files
        )

    async def parse_file(self, file_path: str) -> UnpersistedParseResult:
        """
        Parse a single file and return structured results.

        Args:
            file_path: Path to the file to parse

        Returns:
            FileParseResult object
        """

        # Check if the path exists
        resolved_path = resolve_path(path_str=file_path)
        if not await file_exists_at_path(file_path=resolved_path):
            raise FileNotFoundError(f"Directory does not exist: {file_path}")

        # Load language parsers for all files
        language_parsers = await self._load_parsers(files=[file_path])

        # Parse each file
        with session_scope(self.db_manager) as session:
            ext = get_file_extension(file_path)
            language = get_language_name(ext)

            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()

            parser_info = language_parsers.get(ext)
            if not parser_info:
                raise ValueError(
                    f"No parser available for extension {ext} in file {file_path}"
                )

            file = FileModel(
                file_path=resolved_path,
                language=language,
                file_content=file_content,
            )
            session.add(file)
            session.flush()

            file_result = self._parse_file_to_json(
                file_path=resolved_path,
                language=language,
                file_content=file_content,
                parser_info=parser_info,
            )

        return file_result


# Global instance for convenience
_global_parser: ASTParser | None = None


def get_parser(db_manager: DatabaseManager) -> ASTParser:
    """Get the global parser instance."""
    global _global_parser
    if _global_parser is None:
        _global_parser = ASTParser(db_manager)
    return _global_parser


async def parse_file(
    file_path: str, db_manager: DatabaseManager
) -> UnpersistedParseResult:
    """
    Convenience function to parse a single file.

    Args:
        file_path: Path to the file to parse

    Returns:
        FileParseResult object
    """
    return await get_parser(db_manager).parse_file(file_path)


async def parse_and_persist_repo(
    dir_path: str,
    db_manager: DatabaseManager,
    new_commit_hash: str | None = None,
) -> None:
    """
    Convenience function to recursively parse a directory.

    Args:
        dir_path: Directory path to parse

    Returns:
        ParsedASTResult object
    """
    parser = get_parser(db_manager)
    _ = await parser.recursive_parse_directory(dir_path, new_commit_hash)


async def parse_and_persist_repo_with_delta(
    dir_path: str,
    db_manager: DatabaseManager,
    new_commit_hash: str | None = None,
) -> tuple[ParsedASTResult, ParseDelta | None]:
    """Like parse_and_persist_repo, but returns the parse result and change delta."""
    parser = get_parser(db_manager)
    result = await parser.recursive_parse_directory(dir_path, new_commit_hash)
    return result, parser.current_delta
