"""SQLAlchemy database models."""

from datetime import timezone, datetime
from enum import Enum
from typing import override
from sqlalchemy.sql.schema import Index, UniqueConstraint
from sqlalchemy import (
    Integer,
    String,
    Text,
    Boolean,
    ForeignKey,
    CheckConstraint,
    DateTime,
    LargeBinary,
)
from sqlalchemy.orm import (
    relationship,
    Mapped,
    mapped_column,
    DeclarativeBase,
    MappedAsDataclass,
)


class DefinitionKind(Enum):
    """Enumeration of possible definition kinds"""

    FUNCTION = "function"
    CLASS = "class"
    INTERFACE = "interface"
    TYPE = "type"
    VARIABLE = "variable"
    CONSTRUCTOR = "constructor"
    ENUM = "enum"
    MODULE = "module"


class Base(MappedAsDataclass, DeclarativeBase):  # pyright: ignore[reportUnsafeMultipleInheritance]
    pass


class RepositoryModel(Base):
    """SQLAlchemy model for git repositories table."""

    __tablename__ = "repositories"  # pyright: ignore[reportUnannotatedClassAttribute]

    @override
    def __repr__(self):
        # Only include identifiers or simple columns that won't lazy-load
        return f"<RepositoryModel id={self.id!r} remote_origin_url={self.remote_origin_url!r}>"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )

    repo_slug: Mapped[str] = mapped_column(String, nullable=False)

    # Basic repository identification
    remote_origin_url: Mapped[str | None] = mapped_column(String, nullable=False)
    commit_hash: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    default_branch: Mapped[str | None] = mapped_column(
        String, nullable=True, default="main"
    )

    packages: Mapped[list["PackageModel"]] = relationship(
        "PackageModel",
        back_populates="repository",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
    )

    # Indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_repositories_remote_origin_url", "remote_origin_url"),
        Index("idx_repositories_commit", "commit_hash"),
        UniqueConstraint("remote_origin_url", "commit_hash"),
    )


class FileModel(Base):
    """SQLAlchemy model for files table."""

    __tablename__ = "files"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    package_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("packages.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
        init=False,
    )
    file_path: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    file_content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False)
    last_modified: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    ai_short_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    # Simple relationships
    package: Mapped["PackageModel | None"] = relationship(
        "PackageModel", back_populates="files", default=None
    )
    definitions: Mapped[list["DefinitionModel"]] = relationship(
        "DefinitionModel",
        back_populates="file",
        cascade="all, delete-orphan",
        default_factory=list,
        foreign_keys="[DefinitionModel.file_id]",
        init=False,
    )
    imports: Mapped[list["ImportModel"]] = relationship(
        "ImportModel",
        back_populates="file",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
    )

    file_dependencies: Mapped[list["FileDependencyModel"]] = relationship(
        "FileDependencyModel",
        cascade="all, delete-orphan",
        foreign_keys="[FileDependencyModel.from_file_id]",
        default_factory=list,
        init=False,
        viewonly=True,  # This is a read-only relationship
    )

    file_dependents: Mapped[list["FileDependencyModel"]] = relationship(
        "FileDependencyModel",
        cascade="all, delete-orphan",
        foreign_keys="[FileDependencyModel.to_file_id]",
        default_factory=list,
        init=False,
        viewonly=True,  # This is a read-only relationship
    )

    # Indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_files_path", "file_path"),
        Index("idx_files_language", "language"),
        Index("idx_files_package", "package_id"),
    )


class PackageModel(Base):
    """SQLAlchemy model for packages table."""

    __tablename__ = "packages"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    repository_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("repositories.id", ondelete="CASCADE"),
        nullable=False,
        init=False,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    path: Mapped[str] = mapped_column(String, nullable=False)  # Relative to repo root
    entry_point: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    workspace_type: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )  # pnpm, turbo, yarn, etc.
    is_workspace_root: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    readme_content: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    # Relationships
    repository: Mapped["RepositoryModel"] = relationship(
        "RepositoryModel", back_populates="packages", default=None
    )
    files: Mapped[list["FileModel"]] = relationship(
        "FileModel",
        foreign_keys="[FileModel.package_id]",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
    )
    imports: Mapped[list["ImportModel"]] = relationship(
        "ImportModel",
        back_populates="target_package",
        foreign_keys="[ImportModel.target_package_id]",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
    )

    # Indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_packages_name", "name"),
        Index("idx_packages_path", "path"),
        Index("idx_packages_workspace_root", "is_workspace_root"),
        Index("idx_packages_repository", "repository_id"),
        UniqueConstraint("repository_id", "path"),
    )


class DefinitionModel(Base):
    """SQLAlchemy model for definitions table."""

    __tablename__ = "definitions"  # pyright: ignore[reportUnannotatedClassAttribute]

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), nullable=False, init=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    definition_type: Mapped[str] = mapped_column(
        String,
        nullable=False,
    )
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_code_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    is_exported: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default_export: Mapped[bool] = mapped_column(Boolean, default=False)
    # is_nested: Mapped[bool] = mapped_column(Boolean, default=False)
    complexity_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )
    ai_summary: Mapped[str | None] = mapped_column(Text, nullable=True, default=None)
    ai_short_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )

    # Simple relationships
    file: Mapped["FileModel"] = relationship(
        "FileModel",
        back_populates="definitions",
        default=None,
        foreign_keys=[file_id],
        init=False,
    )
    references: Mapped[list["ReferenceModel"]] = relationship(
        "ReferenceModel",
        cascade="all, delete-orphan",
        foreign_keys="[ReferenceModel.source_definition_id]",
        default_factory=list,
        init=False,
    )

    definition_dependencies: Mapped[list["DefinitionDependencyModel"]] = relationship(
        "DefinitionDependencyModel",
        back_populates="from_definition",
        foreign_keys="[DefinitionDependencyModel.from_definition_id]",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
        viewonly=True,  # This is a read-only relationship
    )
    definition_dependents: Mapped[list["DefinitionDependencyModel"]] = relationship(
        "DefinitionDependencyModel",
        back_populates="to_definition",
        foreign_keys="[DefinitionDependencyModel.to_definition_id]",
        cascade="all, delete-orphan",
        default_factory=list,
        init=False,
        viewonly=True,  # This is a read-only relationship
    )

    # Constraints and indexes
    __table_args__: tuple[UniqueConstraint, Index, Index, Index, Index] = (
        UniqueConstraint("file_id", "name", "start_line", "definition_type"),
        Index("idx_definitions_file_type", "file_id", "definition_type"),
        Index("idx_definitions_name", "name"),
        Index("idx_definitions_exported", "is_exported"),
        Index("idx_definitions_source_code_hash", "source_code_hash"),
    )


class ReferenceModel(Base):
    """SQLAlchemy model for function_calls table."""

    __tablename__ = "references"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    reference_name: Mapped[str] = mapped_column(String, nullable=False)
    reference_type: Mapped[str | None] = mapped_column(
        String,
        CheckConstraint("reference_type IN ('local', 'imported', 'unknown')"),
        nullable=True,
    )

    # Relationships
    source_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("definitions.id", ondelete="CASCADE"),
        nullable=False,
        init=False,
    )
    source_definition: Mapped["DefinitionModel"] = relationship(
        back_populates="references",
        foreign_keys=[source_definition_id],
    )

    target_definition_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("definitions.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )

    # Relationships
    target_definition: Mapped["DefinitionModel | None"] = relationship(
        foreign_keys=[target_definition_id],
        default=None,
    )

    # Indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_references_source", "source_definition_id"),
        Index("idx_references_target", "target_definition_id"),
        UniqueConstraint("source_definition_id", "target_definition_id"),
    )


### no longer used
class ImportModel(Base):
    """SQLAlchemy model for imports table."""

    __tablename__ = "imports"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), init=False
    )
    specifier: Mapped[str] = mapped_column(String, nullable=False)
    module: Mapped[str] = mapped_column(String, nullable=False)
    import_type: Mapped[str] = mapped_column(
        String,
        CheckConstraint(
            "import_type IN ('default', 'named', 'namespace', 'side-effect', 're-export')"
        ),
        nullable=False,
    )
    resolved_file_path: Mapped[str | None] = mapped_column(String, nullable=True)
    alias: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    is_external: Mapped[bool] = mapped_column(Boolean, default=False)

    # New fields for package tracking
    target_package_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("packages.id", ondelete="SET NULL"),
        nullable=True,
        default=None,
    )
    resolution_type: Mapped[str | None] = mapped_column(
        String,
        CheckConstraint(
            "resolution_type IN ('package', 'alias', 'relative', 'external', 'unknown')"
        ),
        nullable=True,
        default=None,
    )

    # Relationships
    file: Mapped["FileModel"] = relationship(
        "FileModel", back_populates="imports", default=None
    )
    target_package: Mapped["PackageModel | None"] = relationship(
        "PackageModel",
        back_populates="imports",
        default=None,
        foreign_keys=[target_package_id],
    )

    # Indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_imports_file", "file_id"),
        Index("idx_imports_module", "module"),
        Index("idx_imports_target_package", "target_package_id"),
        Index("idx_imports_resolution_type", "resolution_type"),
    )


class DefinitionDependencyModel(Base):
    """SQLAlchemy model for dependencies table."""

    __tablename__ = "definition_dependencies"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    from_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("definitions.id", ondelete="CASCADE"),
        nullable=False,
        init=False,
    )
    to_definition_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("definitions.id", ondelete="CASCADE"),
        nullable=False,
        init=False,
    )
    dependency_type: Mapped[str] = mapped_column(
        String,
        CheckConstraint("dependency_type IN ('reference', 'inheritence', 'import')"),
        nullable=False,
    )
    strength: Mapped[int] = mapped_column(Integer, default=1)

    from_definition: Mapped["DefinitionModel"] = relationship(
        "DefinitionModel",
        foreign_keys=[from_definition_id],
        back_populates="definition_dependencies",
        default=None,
    )
    to_definition: Mapped["DefinitionModel"] = relationship(
        "DefinitionModel",
        foreign_keys=[to_definition_id],
        back_populates="definition_dependents",
        default=None,
    )

    # Constraints and indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        UniqueConstraint("from_definition_id", "to_definition_id"),
        Index("idx_dependencies_dependent", "from_definition_id"),
        Index("idx_dependencies_dependency", "to_definition_id"),
        Index("idx_dependencies_type", "dependency_type"),
    )


class FileDependencyModel(Base):
    """SQLAlchemy model for file dependencies table."""

    __tablename__ = "file_dependencies"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    from_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), init=False
    )
    to_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("files.id", ondelete="CASCADE"), init=False
    )
    from_file: Mapped["FileModel"] = relationship(
        "FileModel",
        foreign_keys=[from_file_id],
        back_populates="file_dependencies",
        default=None,
    )
    to_file: Mapped["FileModel"] = relationship(
        "FileModel",
        foreign_keys=[to_file_id],
        back_populates="file_dependents",
        default=None,
    )

    # Constraints and indexes
    __table_args__ = (  # pyright: ignore[reportAny, reportUnannotatedClassAttribute]
        Index("idx_file_dependencies_from", "from_file_id"),
        Index("idx_file_dependencies_to", "to_file_id"),
        UniqueConstraint("from_file_id", "to_file_id"),
    )


class EmbeddingModel(Base):
    """SQLAlchemy model for vector embeddings stored locally in SQLite.

    This table stores metadata alongside the raw embedding vector bytes (float32 array).
    A unique constraint on (entity_type, entity_id) enables idempotent upserts.

    A separate sqlite-vec virtual table (created at runtime) can index these
    embeddings for efficient similarity search. The virtual table uses the rowid
    to reference rows in this table.
    """

    __tablename__ = "embeddings"  # pyright: ignore[reportUnannotatedClassAttribute]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )

    # Uniquely identifies what this embedding represents
    entity_type: Mapped[str] = mapped_column(
        String,
        CheckConstraint("entity_type IN ('file', 'definition')"),
        nullable=False,
    )
    entity_id: Mapped[int] = mapped_column(Integer, nullable=False)

    # Embedding info
    embedding_model: Mapped[str] = mapped_column(String, nullable=False)
    embedding_dims: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

    # Helpful context for filtering and display
    entity_name: Mapped[str] = mapped_column(String, nullable=False)
    file_path: Mapped[str] = mapped_column(String, nullable=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True, default=None)
    definition_type: Mapped[str | None] = mapped_column(
        String, nullable=True, default=None
    )
    is_exported: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, default=None
    )
    complexity_score: Mapped[int | None] = mapped_column(
        Integer, nullable=True, default=None
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default_factory=lambda: datetime.now(timezone.utc), init=False
    )

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id"),
        Index("idx_embeddings_entity", "entity_type", "entity_id"),
        Index("idx_embeddings_file_path", "file_path"),
        Index("idx_embeddings_language", "language"),
    )
