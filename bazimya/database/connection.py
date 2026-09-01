"""Database connections.

SQLite is the default and needs nothing installed — which matters on shared
hosting, where you often cannot add a database through a control panel without
paying for it. MySQL and Postgres are supported through optional drivers.

Every driver is used through DB-API 2.0, and the only thing that really
differs between them is the placeholder style, which is normalised here so the
query builder can emit one dialect.
"""

import os
import re
import sqlite3
import threading

#: Placeholders are written as ? everywhere and rewritten per driver.
_PLACEHOLDER = re.compile(r"\?")


class ConnectionError_(RuntimeError):
    """Raised when a connection cannot be opened, with advice on the fix."""


class QueryError(RuntimeError):
    """A statement failed. Carries the SQL and bindings, because a message
    without them is nearly useless when debugging a builder."""

    def __init__(self, message, sql=None, bindings=None):
        self.sql = sql
        self.bindings = bindings

        if sql:
            message = "{}\n\n  SQL: {}\n  Bindings: {!r}".format(message, sql, bindings)

        super().__init__(message)


class Connection:
    def __init__(self, config=None, base_path=""):
        self.config = dict(config or {})
        self.base_path = base_path
        self.driver = str(self.config.get("driver", "sqlite")).lower()
        self._connection = None
        self._lock = threading.RLock()
        self._transactions = 0
        self.logging = False
        self._log = []

    # -- opening ----------------------------------------------------------

    def connection(self):
        if self._connection is None:
            self._connection = self._connect()

        return self._connection

    def _connect(self):
        if self.driver == "sqlite":
            return self._connect_sqlite()

        if self.driver in ("mysql", "mariadb"):
            return self._connect_mysql()

        if self.driver in ("pgsql", "postgres", "postgresql"):
            return self._connect_postgres()

        raise ConnectionError_(
            "Unknown database driver [{}]. Use sqlite, mysql or pgsql.".format(self.driver)
        )

    def _connect_sqlite(self):
        database = str(self.config.get("database", "database/database.sqlite"))

        if database != ":memory:":
            if not os.path.isabs(database):
                database = os.path.join(self.base_path, database)

            directory = os.path.dirname(database)

            if directory and not os.path.isdir(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                except OSError as error:
                    raise ConnectionError_(
                        "Could not create {} for the SQLite database: {}".format(directory, error)
                    ) from error

        try:
            connection = sqlite3.connect(database, timeout=15, isolation_level=None)
        except sqlite3.Error as error:
            raise ConnectionError_(
                "Could not open the SQLite database at {}: {}".format(database, error)
            ) from error

        connection.row_factory = sqlite3.Row

        # Foreign keys are off by default in SQLite, which quietly turns every
        # constraint in a migration into a comment.
        connection.execute("PRAGMA foreign_keys = ON")

        # WAL survives concurrent readers far better under a web server.
        if database != ":memory:":
            try:
                connection.execute("PRAGMA journal_mode = WAL")
            except sqlite3.Error:
                # Some shared hosts put the database on a filesystem that
                # cannot do WAL. The default journal still works.
                pass

        return connection

    def _connect_mysql(self):
        try:
            import pymysql
            from pymysql.cursors import DictCursor
        except ImportError as error:
            raise ConnectionError_(
                "MySQL needs the PyMySQL driver:\n\n    pip install PyMySQL\n\n"
                "PyMySQL is pure Python, so it installs on shared hosting where "
                "mysqlclient will not."
            ) from error

        try:
            return pymysql.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 3306) or 3306),
                user=self.config.get("username", "root"),
                password=self.config.get("password", "") or "",
                database=self.config.get("database", ""),
                charset=self.config.get("charset", "utf8mb4"),
                cursorclass=DictCursor,
                autocommit=True,
            )
        except Exception as error:  # noqa: BLE001 — driver exceptions vary
            raise ConnectionError_("Could not connect to MySQL: {}".format(error)) from error

    def _connect_postgres(self):
        try:
            import psycopg2
            import psycopg2.extras
        except ImportError as error:
            raise ConnectionError_(
                "Postgres needs psycopg2:\n\n    pip install psycopg2-binary"
            ) from error

        try:
            connection = psycopg2.connect(
                host=self.config.get("host", "127.0.0.1"),
                port=int(self.config.get("port", 5432) or 5432),
                user=self.config.get("username", "postgres"),
                password=self.config.get("password", "") or "",
                dbname=self.config.get("database", ""),
                cursor_factory=psycopg2.extras.RealDictCursor,
            )
            connection.autocommit = True

            return connection
        except Exception as error:  # noqa: BLE001
            raise ConnectionError_("Could not connect to Postgres: {}".format(error)) from error

    # -- dialect ----------------------------------------------------------

    def placeholder_style(self):
        return "?" if self.driver == "sqlite" else "%s"

    def prepare(self, sql):
        """Rewrite ? placeholders for drivers that want %s."""
        if self.driver == "sqlite":
            return sql

        return _PLACEHOLDER.sub("%s", sql)

    def wrap(self, identifier):
        """Quote a table or column name for this driver."""
        if identifier == "*":
            return "*"

        # Already qualified (table.column) — wrap each half.
        if "." in identifier:
            return ".".join(self.wrap(part) for part in identifier.split("."))

        if self.driver in ("mysql", "mariadb"):
            return "`{}`".format(identifier.replace("`", ""))

        return '"{}"'.format(identifier.replace('"', ""))

    # -- running statements -----------------------------------------------

    def select(self, sql, bindings=None):
        """Run a query and return a list of dicts."""
        cursor = self._execute(sql, bindings)

        try:
            rows = cursor.fetchall()
        finally:
            cursor.close()

        return [self._to_dict(row) for row in rows]

    def select_one(self, sql, bindings=None):
        rows = self.select(sql, bindings)

        return rows[0] if rows else None

    def insert(self, sql, bindings=None):
        """Run an INSERT and return the new row's id."""
        cursor = self._execute(sql, bindings)

        try:
            return cursor.lastrowid
        finally:
            cursor.close()

    def update(self, sql, bindings=None):
        return self.affecting(sql, bindings)

    def delete(self, sql, bindings=None):
        return self.affecting(sql, bindings)

    def affecting(self, sql, bindings=None):
        cursor = self._execute(sql, bindings)

        try:
            return cursor.rowcount
        finally:
            cursor.close()

    def statement(self, sql, bindings=None):
        cursor = self._execute(sql, bindings)
        cursor.close()

        return True

    def _execute(self, sql, bindings=None):
        bindings = list(bindings or [])
        prepared = self.prepare(sql)

        with self._lock:
            try:
                cursor = self.connection().cursor()
                cursor.execute(prepared, bindings)
            except Exception as error:  # noqa: BLE001 — driver exceptions vary
                raise QueryError(str(error), sql, bindings) from error

        if self.logging:
            self._log.append({"sql": sql, "bindings": bindings})

        return cursor

    @staticmethod
    def _to_dict(row):
        if isinstance(row, dict):
            return dict(row)

        if isinstance(row, sqlite3.Row):
            return {key: row[key] for key in row.keys()}

        return dict(row)

    # -- transactions -----------------------------------------------------

    def transaction(self, callback):
        """Run a callback in a transaction, rolling back if it raises."""
        self.begin()

        try:
            result = callback()
        except Exception:
            self.rollback()
            raise

        self.commit()

        return result

    def begin(self):
        with self._lock:
            if self._transactions == 0:
                self.statement("BEGIN")

            self._transactions += 1

    def commit(self):
        with self._lock:
            if self._transactions <= 1:
                self.connection().commit() if self.driver != "sqlite" else self.statement("COMMIT")
                self._transactions = 0
            else:
                self._transactions -= 1

    def rollback(self):
        with self._lock:
            if self._transactions <= 1:
                self.connection().rollback() if self.driver != "sqlite" else self.statement("ROLLBACK")
                self._transactions = 0
            else:
                self._transactions -= 1

    # -- query builder entry point ----------------------------------------

    def table(self, name):
        from .query import QueryBuilder

        return QueryBuilder(self, name)

    # -- introspection ----------------------------------------------------

    def enable_query_log(self):
        self.logging = True

        return self

    def query_log(self):
        return list(self._log)

    def flush_query_log(self):
        self._log = []

    def close(self):
        if self._connection is not None:
            try:
                self._connection.close()
            finally:
                self._connection = None

    def __repr__(self):
        return "<Connection {}>".format(self.driver)
