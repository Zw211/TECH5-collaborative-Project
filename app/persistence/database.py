"""Database connection and lifecycle manager for SQLite persistence.

This module manages connections, transactions, foreign keys, and schema
initialization for TECH5.
"""

import contextlib
import pathlib
import sqlite3
from collections.abc import Iterator
from typing import Any

from app import config


class InvalidDatabaseRecords(ValueError):
    """Identifies saved records that cannot safely be used as run inputs."""

    def __init__(self, errors: list[str]) -> None:
        """Retain the saved-record errors for the error page.

        Args:
            errors: Validation messages identifying invalid saved records.
        """
        self.errors = list(errors)
        super().__init__("; ".join(errors))


def read_boolean(value: object, field: str) -> bool:
    """Convert SQLite flags without treating nonempty text as true.

    Args:
        value: Raw flag loaded from SQLite.
        field: Record and field description used in diagnostics.

    Returns:
        The boolean represented by integer 0 or 1.

    Raises:
        InvalidDatabaseRecords: The value is not an integer 0 or 1.
    """
    if type(value) is not int or value not in (0, 1):
        raise InvalidDatabaseRecords(
            [f"{field}: saved mandatory flag must be 0 or 1."]
        )
    return bool(value)


class DatabaseManager:
    """Manages SQLite database connections and transactions."""

    def __init__(
        self,
        db_path: pathlib.Path | str | None = None,
        timeout_seconds: float = 30.0,
        *,
        transaction_connection: sqlite3.Connection | None = None,
    ) -> None:
        """Initializes the database manager with target file path.

        Args:
            db_path: Optional custom path to SQLite database file.
            timeout_seconds: How long to wait for a locked database.
            transaction_connection: Internal connection shared by transaction().
        """
        if db_path is None:
            self.db_path = config.Config.DATABASE_PATH
        elif isinstance(db_path, str):
            self.db_path = pathlib.Path(db_path)
        else:
            self.db_path = db_path

        self.timeout_seconds = timeout_seconds
        self._transaction_connection = transaction_connection

    def get_connection(self) -> sqlite3.Connection:
        """Creates and configures a new SQLite connection.

        Returns:
            An active SQLite Connection configured with Row factory and FKs.
        """
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            raise sqlite3.OperationalError(
                "The database folder is unavailable."
            ) from error
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=self.timeout_seconds,
            detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
        )
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.Error:
            conn.close()
            raise
        return conn

    def check_input_integrity(self) -> None:
        """Check references and raw flags before loading saved records.

        Other input types/ranges are checked by the domain validator after
        loading. This method neither repairs nor drops invalid records.
        """
        errors: list[str] = []
        with self.connection() as conn:
            for row in conn.execute("PRAGMA foreign_key_check;"):
                errors.append(
                    f"Table '{row['table']}', row {row['rowid']}: "
                    f"a reference to '{row['parent']}' has no matching record."
                )
            rows = conn.execute(
                "SELECT project_id, skill_id, is_mandatory FROM "
                "project_requirements;"
            )
            for row in rows:
                try:
                    read_boolean(
                        row["is_mandatory"],
                        f"Project '{row['project_id']}', skill "
                        f"'{row['skill_id']}'",
                    )
                except InvalidDatabaseRecords as error:
                    errors.extend(error.errors)
        if errors:
            raise InvalidDatabaseRecords(errors)

    @contextlib.contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager yielding a managed connection with transaction.

        Yields:
            An active sqlite3.Connection.
        """
        if self._transaction_connection is not None:
            yield self._transaction_connection
            return
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextlib.contextmanager
    def transaction(self) -> Iterator["DatabaseManager"]:
        """Share one transaction across participating repositories.

        The owning connection commits on success and rolls back on error.
        Repository calls using the yielded manager cannot commit separately.

        Yields:
            A manager bound to the transaction's shared connection.
        """
        with self.connection() as conn:
            yield DatabaseManager(
                self.db_path, self.timeout_seconds, transaction_connection=conn
            )

    def initialize_schema(self) -> None:
        """Executes the DDL schema script to establish tables and indexes."""
        schema_path = pathlib.Path(__file__).parent / "schema.sql"
        with open(schema_path, mode="r", encoding="utf-8") as f:
            ddl_script = f.read()

        with self.connection() as conn:
            conn.executescript(ddl_script)

    def execute_query(
        self,
        query: str,
        params: dict[str, Any] | tuple[Any, ...] | None = None,
    ) -> list[sqlite3.Row]:
        """Executes a parameterized SELECT query and returns all rows.

        Args:
            query: The SQL query text.
            params: Parameters for SQL substitution.

        Returns:
            List of sqlite3.Row objects.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            if params is None:
                cursor.execute(query)
            else:
                cursor.execute(query, params)
            return cursor.fetchall()

    def execute_statement(
        self,
        statement: str,
        params: dict[str, Any] | tuple[Any, ...] | None = None,
    ) -> int:
        """Executes an INSERT, UPDATE, or DELETE statement.

        Args:
            statement: The SQL statement text.
            params: Parameters for SQL substitution.

        Returns:
            The rowcount of modified records.
        """
        with self.connection() as conn:
            cursor = conn.cursor()
            if params is None:
                cursor.execute(statement)
            else:
                cursor.execute(statement, params)
            return cursor.rowcount


# Singleton default instance
db_manager = DatabaseManager()
