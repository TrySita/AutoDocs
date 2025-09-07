"""Database connection and management utilities."""

from collections.abc import Generator
from contextvars import ContextVar
from typing import Any
from contextlib import contextmanager
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base
import logging


# Helper functions to get DB session

# Context variable to store current session
_session_context: ContextVar[Session | None] = ContextVar("db_session", default=None)


def get_current_session() -> Session:
    """Get the current session from context.

    Returns:
        Current database session

    Raises:
        RuntimeError: If no session is found in context
    """
    session = _session_context.get()
    if session is None:
        raise RuntimeError(
            "No database session found in context. "
            + "Use session_scope() context manager to provide a session."
        )
    return session


def set_session_context(session: Session | None) -> None:
    """Set the current session in context.

    Args:
        session: Database session to set, or None to clear
    """
    _ = _session_context.set(session)


@contextmanager
def session_scope(db_manager: "DatabaseManager") -> Generator[Session, None, None]:
    """Context manager that provides session scope for database operations.

    This creates a new database session and sets it in the context variable,
    making it available to all functions called within this scope without
    explicit parameter passing.

    Args:
        db_manager: Database manager to create session from

    Yields:
        Database session that will be available via get_current_session()

    Example:
        with session_scope(db_manager) as session:
            # All methods called here can use get_current_session()
            query_interface = QueryInterface(db_manager)
            results = query_interface.find_definition_by_name("MyClass")
            # session is automatically committed on success or rolled back on error
    """
    with db_manager.get_session() as session:
        # Store previous session context (in case of nested scopes)
        previous_session = _session_context.get()

        try:
            # Set new session in context
            _ = _session_context.set(session)
            yield session
        finally:
            # Restore previous context
            _ = _session_context.set(previous_session)


def has_session_context() -> bool:
    """Check if there is a session available in the current context.

    Returns:
        True if a session is available, False otherwise
    """
    return _session_context.get() is not None


class DatabaseManager:
    """Manages SQLite/Turso database connections and schema."""

    def __init__(
        self,
        db_path: str = ":memory:",
        echo: bool = False,
        expire_on_commit: bool = True,
    ):
        """Initialize database manager.

        Args:
            db_path: Path to SQLite database file or ":memory:" for in-memory (ignored if using embedded replica)
            echo: Whether to echo SQL statements for debugging
            expire_on_commit: Whether to expire objects on commit
            turso_url: Turso database URL (if None, will check TURSO_DATABASE_URL env var)
            turso_auth_token: Turso auth token (if None, will check TURSO_AUTH_TOKEN env var)
            turso_embedded_path: Path for embedded replica database file
            turso_sync_url: Remote Turso database URL to sync with for embedded replicas
            turso_sync_interval: Automatic sync interval in seconds
            turso_encryption_key: Encryption key for embedded replica (optional)
        """
        self.db_path = db_path
        self.echo = echo
        self._expire_on_commit = expire_on_commit
        self._initialize_engine_and_session()

    def _initialize_engine_and_session(self) -> None:
        """Initialize the database engine and session factory."""

        # Local SQLite connection
        connect_args = {
            "check_same_thread": False,
        }
        if self.db_path == ":memory:":
            # For in-memory databases, use StaticPool to persist across connections
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=self.echo,
                connect_args=connect_args,
                poolclass=StaticPool,
            )
        else:
            self.engine = create_engine(
                f"sqlite:///{self.db_path}",
                echo=self.echo,
                connect_args=connect_args,
            )

        print(f"connecting to db at {self.db_path}")

        # Configure SQLite pragmas for better performance (local SQLite only)
        @event.listens_for(self.engine, "connect")
        def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
            cursor = dbapi_connection.cursor()
            # Enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys=ON")
            # Set journal mode to WAL for better concurrency
            cursor.execute("PRAGMA journal_mode=WAL")
            # Set synchronous mode to NORMAL for better performance
            cursor.execute("PRAGMA synchronous=NORMAL")
            # Increase cache size
            cursor.execute("PRAGMA cache_size=10000")
            # Set temp store to memory
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.close()

        # Load sqlite-vec extension on connect (best-effort)
        def _load_sqlite_vec(dbapi_connection: Any, _) -> None:  # noqa: ANN401
            try:
                import sqlite_vec

                dbapi_connection.enable_load_extension(True)
                sqlite_vec.load(dbapi_connection)  # type: ignore[attr-defined]
            except Exception as e:  # pragma: no cover - best effort
                raise e

        event.listen(self.engine, "connect", _load_sqlite_vec)

        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine,
            expire_on_commit=self._expire_on_commit,
        )

        self.create_tables()
        self.create_fts_indexes()
        # Create sqlite-vec virtual table for vector search (1536 dims default)
        self.create_vector_indexes()

    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def create_fts_indexes(self) -> None:
        """Create FTS indexes for full-text search."""
        with self.engine.begin() as session:
            _ = session.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS definitions_name_fts \
                    USING fts5(name, content='definitions', content_rowid='id', tokenize='unicode61 remove_diacritics 2', prefix='2 3 4')"
            )
            # Definitions FTS index triggers (split into individual statements)
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS definitions_ai AFTER INSERT ON definitions BEGIN
                    INSERT INTO definitions_name_fts(rowid, name) VALUES (new.id, new.name);
                END;
                """
            )
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS definitions_au AFTER UPDATE OF name ON definitions BEGIN
                    UPDATE definitions_name_fts SET name=new.name WHERE rowid=new.id;
                END;
                """
            )
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS definitions_ad AFTER DELETE ON definitions BEGIN
                    DELETE FROM definitions_name_fts WHERE rowid=old.id;
                END;
                """
            )

            # File path FTS index
            _ = session.exec_driver_sql(
                "CREATE VIRTUAL TABLE IF NOT EXISTS files_path_fts \
                    USING fts5(file_path, content='files', content_rowid='id', tokenize='unicode61 remove_diacritics 2', prefix='2 3 4')"
            )
            # Files FTS index triggers (split into individual statements)
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS files_ai AFTER INSERT ON files BEGIN
                    INSERT INTO files_path_fts(rowid, file_path) VALUES (new.id, new.file_path);
                END;
                """
            )
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS files_au AFTER UPDATE OF file_path ON files BEGIN
                    UPDATE files_path_fts SET file_path=new.file_path WHERE rowid=new.id;
                END;
                """
            )
            _ = session.exec_driver_sql(
                """
                CREATE TRIGGER IF NOT EXISTS files_ad AFTER DELETE ON files BEGIN
                    DELETE FROM files_path_fts WHERE rowid=old.id;
                END;
                """
            )

    def create_vector_indexes(self, dims: int = 1536) -> None:
        """Create sqlite-vec virtual table for embeddings.

        Args:
            dims: Dimensionality of the embedding vectors. Defaults to 1536.
        """
        # Note: The sqlite-vec extension must be loaded on the connection. The
        # connect hook above tries to load it automatically; if loading fails,
        # this statement will raise which we swallow to keep DB usable without vectors.
        try:
            with self.get_session() as session:
                _ = session.execute(
                    text(
                        f"CREATE VIRTUAL TABLE IF NOT EXISTS embeddings_vec USING vec0(embedding float[{dims}])"
                    )
                )
        except Exception as e:  # pragma: no cover - best effort
            logging.getLogger(__name__).warning(
                f"Failed to create sqlite-vec virtual table: {e}"
            )

    def drop_tables(self) -> None:
        """Drop all database tables."""
        Base.metadata.drop_all(bind=self.engine)

    def reset_database(self) -> None:
        """Drop and recreate all tables."""
        self.drop_tables()
        self.create_tables()

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def get_session_generator(self) -> Generator[Session, None, None]:
        """Get a database session with automatic cleanup."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def execute_raw_sql(
        self, sql: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute raw SQL and return results as dictionaries.

        Args:
            sql: SQL query to execute
            params: Optional parameters for the query

        Returns:
            List of dictionaries representing query results
        """
        with self.get_session() as session:
            result = session.execute(text(sql), params or {})
            columns = result.keys()
            return [dict(zip(columns, row)) for row in result.fetchall()]

    def get_table_info(self, table_name: str) -> list[dict[str, Any]]:
        """Get information about a table's structure.

        Args:
            table_name: Name of the table to inspect

        Returns:
            List of dictionaries with column information
        """
        sql = f"PRAGMA table_info({table_name})"
        return self.execute_raw_sql(sql)

    def get_all_tables(self) -> list[str]:
        """Get list of all tables in the database.

        Returns:
            List of table names
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table'"
        result = self.execute_raw_sql(sql)
        return [row["name"] for row in result]

    def optimize_database(self) -> None:
        """Run database optimization commands."""
        with self.get_session() as session:
            # Analyze tables for query optimization
            session.execute(text("ANALYZE"))
            # Vacuum database to reclaim space
            session.execute(text("VACUUM"))

    def close(self) -> None:
        """Close database connection and dispose of engine."""
        if hasattr(self, "engine"):
            self.engine.dispose()

    # -----------------------------
    # Vector search helper
    # -----------------------------

    def query_nearest_neighbors(
        self,
        query_vector: list[float],
        top_k: int = 10,
        entity_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find nearest neighbors using sqlite-vec and return embedding rows + distance.

        Args:
            query_vector: Embedding vector to search with (float list)
            top_k: Maximum number of neighbors to return
            entity_type: Optional filter ("file" or "definition")

        Returns:
            List of dicts with columns from embeddings plus `distance`.
        """
        from array import array

        packed = array("f", query_vector).tobytes()
        params: dict[str, Any] = {"embedding": packed, "k": top_k}

        sql = (
            "SELECT e.id, e.entity_type, e.entity_id, e.entity_name, e.file_path, e.language, e.definition_type,"
            " e.embedding_model, e.embedding_dims, e.created_at, v.distance,"
            " CASE WHEN e.entity_type='file' THEN f.ai_summary ELSE d.ai_summary END AS ai_summary "
            "FROM embeddings_vec v JOIN embeddings e ON e.id = v.rowid "
            "LEFT JOIN files f ON (e.entity_type='file' AND f.id = e.entity_id) "
            "LEFT JOIN definitions d ON (e.entity_type='definition' AND d.id = e.entity_id) "
            "WHERE v.embedding MATCH :embedding AND v.k = :k "
        )
        if entity_type:
            sql += "AND e.entity_type = :entity_type "
            params["entity_type"] = entity_type
        # Keep LIMIT :k as a safety cap; vec0 requires either literal LIMIT or k constraint.
        sql += "ORDER BY v.distance LIMIT :k"

        with self.get_session() as session:
            result = session.execute(text(sql), params)
            cols = result.keys()
            return [dict(zip(cols, row)) for row in result.fetchall()]
