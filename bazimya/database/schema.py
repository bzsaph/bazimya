"""The schema builder.

Migrations describe tables rather than writing SQL by hand:

    def up(self):
        with Schema.create('posts') as table:
            table.id()
            table.string('title')
            table.text('body').nullable()
            table.foreign_id('user_id').references('id').on('users').on_delete('cascade')
            table.timestamps()

The three drivers disagree about auto-increment, booleans and adding
constraints after the fact, so each column type is rendered per driver rather
than assuming one dialect and hoping.
"""

from ..support.aliases import AliasMeta, AliasMixin
from .query import _identifier


class Column(AliasMixin):
    def __init__(self, name, type_name, **options):
        self.name = _identifier(name)
        self.type_name = type_name
        self.options = dict(options)
        self.is_nullable = False
        self.default_value = _NO_DEFAULT
        self.is_unique = False
        self.is_index = False
        self.is_primary = False
        self.is_unsigned = False
        self.auto_increment = False
        self.foreign = None

    # -- modifiers --------------------------------------------------------

    def nullable(self, value=True):
        self.is_nullable = bool(value)

        return self

    def default(self, value):
        self.default_value = value

        return self

    def unique(self):
        self.is_unique = True

        return self

    def index(self):
        self.is_index = True

        return self

    def primary(self):
        self.is_primary = True

        return self

    def unsigned(self):
        self.is_unsigned = True

        return self

    def use_current(self):
        self.default_value = _CURRENT_TIMESTAMP

        return self

    # -- foreign keys -----------------------------------------------------

    def references(self, column):
        self.foreign = {"column": column, "table": None, "on_delete": None, "on_update": None}

        return self

    def on(self, table):
        if self.foreign is None:
            raise RuntimeError("Call references() before on().")

        self.foreign["table"] = table

        return self

    def on_delete(self, action):
        if self.foreign is None:
            raise RuntimeError("Call references().on() before on_delete().")

        self.foreign["on_delete"] = action

        return self

    def on_update(self, action):
        if self.foreign is None:
            raise RuntimeError("Call references().on() before on_update().")

        self.foreign["on_update"] = action

        return self

    def cascade_on_delete(self):
        return self.on_delete("cascade")


class _NoDefault:
    def __repr__(self):
        return "<no default>"


class _CurrentTimestamp:
    def __repr__(self):
        return "CURRENT_TIMESTAMP"


_NO_DEFAULT = _NoDefault()
_CURRENT_TIMESTAMP = _CurrentTimestamp()


class Blueprint(AliasMixin):
    """Collects the columns and indexes for one table."""

    def __init__(self, table, mode="create"):
        self.table = _identifier(table, "table")
        self.mode = mode
        self.columns = []
        self.indexes = []
        self.dropped = []
        self.renamed = []

    # -- column types -----------------------------------------------------

    def _add(self, name, type_name, **options):
        column = Column(name, type_name, **options)
        self.columns.append(column)

        return column

    def id(self, name="id"):
        column = self._add(name, "integer")
        column.auto_increment = True
        column.is_primary = True

        return column

    increments = id
    big_increments = id

    def string(self, name, length=255):
        return self._add(name, "string", length=length)

    def char(self, name, length=1):
        return self._add(name, "char", length=length)

    def text(self, name):
        return self._add(name, "text")

    def long_text(self, name):
        return self._add(name, "longtext")

    def integer(self, name):
        return self._add(name, "integer")

    def big_integer(self, name):
        return self._add(name, "biginteger")

    def small_integer(self, name):
        return self._add(name, "smallinteger")

    def boolean(self, name):
        return self._add(name, "boolean")

    def float(self, name):
        return self._add(name, "float")

    def double(self, name):
        return self._add(name, "double")

    def decimal(self, name, precision=8, scale=2):
        return self._add(name, "decimal", precision=precision, scale=scale)

    def date(self, name):
        return self._add(name, "date")

    def datetime(self, name):
        return self._add(name, "datetime")

    def time(self, name):
        return self._add(name, "time")

    def timestamp(self, name):
        return self._add(name, "timestamp")

    def json(self, name):
        return self._add(name, "json")

    def uuid(self, name):
        return self._add(name, "char", length=36)

    def foreign_id(self, name):
        column = self._add(name, "integer")
        column.is_unsigned = True

        return column

    def remember_token(self):
        return self.string("remember_token", 100).nullable()

    def timestamps(self):
        self.timestamp("created_at").nullable()
        self.timestamp("updated_at").nullable()

    def soft_deletes(self):
        return self.timestamp("deleted_at").nullable()

    # -- indexes ----------------------------------------------------------

    def unique(self, *columns, name=None):
        self.indexes.append({"type": "unique", "columns": list(columns), "name": name})

        return self

    def index(self, *columns, name=None):
        self.indexes.append({"type": "index", "columns": list(columns), "name": name})

        return self

    # -- alterations ------------------------------------------------------

    def drop_column(self, *names):
        self.dropped.extend(names)

        return self

    def rename_column(self, old, new):
        self.renamed.append((old, new))

        return self


class Grammar:
    """Renders a Blueprint as SQL for one driver."""

    TYPES = {
        "sqlite": {
            "string": "VARCHAR({length})",
            "char": "CHAR({length})",
            "text": "TEXT",
            "longtext": "TEXT",
            "integer": "INTEGER",
            "biginteger": "INTEGER",
            "smallinteger": "INTEGER",
            "boolean": "INTEGER",
            "float": "REAL",
            "double": "REAL",
            "decimal": "NUMERIC({precision}, {scale})",
            "date": "DATE",
            "datetime": "DATETIME",
            "time": "TIME",
            "timestamp": "DATETIME",
            "json": "TEXT",
        },
        "mysql": {
            "string": "VARCHAR({length})",
            "char": "CHAR({length})",
            "text": "TEXT",
            "longtext": "LONGTEXT",
            "integer": "INT",
            "biginteger": "BIGINT",
            "smallinteger": "SMALLINT",
            "boolean": "TINYINT(1)",
            "float": "FLOAT",
            "double": "DOUBLE",
            "decimal": "DECIMAL({precision}, {scale})",
            "date": "DATE",
            "datetime": "DATETIME",
            "time": "TIME",
            "timestamp": "TIMESTAMP NULL",
            "json": "JSON",
        },
        "pgsql": {
            "string": "VARCHAR({length})",
            "char": "CHAR({length})",
            "text": "TEXT",
            "longtext": "TEXT",
            "integer": "INTEGER",
            "biginteger": "BIGINT",
            "smallinteger": "SMALLINT",
            "boolean": "BOOLEAN",
            "float": "REAL",
            "double": "DOUBLE PRECISION",
            "decimal": "NUMERIC({precision}, {scale})",
            "date": "DATE",
            "datetime": "TIMESTAMP",
            "time": "TIME",
            "timestamp": "TIMESTAMP",
            "json": "JSONB",
        },
    }

    def __init__(self, connection):
        self.connection = connection
        self.driver = self._normalise(connection.driver)

    @staticmethod
    def _normalise(driver):
        if driver in ("mysql", "mariadb"):
            return "mysql"

        if driver in ("pgsql", "postgres", "postgresql"):
            return "pgsql"

        return "sqlite"

    def wrap(self, name):
        return self.connection.wrap(name)

    # -- statements -------------------------------------------------------

    def compile_create(self, blueprint):
        definitions = [self.column_sql(column) for column in blueprint.columns]

        for column in blueprint.columns:
            if column.foreign and column.foreign["table"]:
                definitions.append(self.foreign_sql(column))

        for index in blueprint.indexes:
            if index["type"] == "unique":
                definitions.append(
                    "UNIQUE ({})".format(", ".join(self.wrap(c) for c in index["columns"]))
                )

        statements = [
            "CREATE TABLE {} (\n    {}\n)".format(
                self.wrap(blueprint.table), ",\n    ".join(definitions)
            )
        ]

        statements.extend(self.compile_indexes(blueprint))

        return statements

    def compile_alter(self, blueprint):
        statements = []

        for column in blueprint.columns:
            statements.append(
                "ALTER TABLE {} ADD COLUMN {}".format(
                    self.wrap(blueprint.table), self.column_sql(column, for_alter=True)
                )
            )

        for name in blueprint.dropped:
            statements.append(
                "ALTER TABLE {} DROP COLUMN {}".format(
                    self.wrap(blueprint.table), self.wrap(name)
                )
            )

        for old, new in blueprint.renamed:
            statements.append(
                "ALTER TABLE {} RENAME COLUMN {} TO {}".format(
                    self.wrap(blueprint.table), self.wrap(old), self.wrap(new)
                )
            )

        statements.extend(self.compile_indexes(blueprint))

        return statements

    def compile_indexes(self, blueprint):
        statements = []

        for index in blueprint.indexes:
            if index["type"] != "index":
                continue

            name = index["name"] or "{}_{}_index".format(
                blueprint.table, "_".join(index["columns"])
            )
            statements.append(
                "CREATE INDEX {} ON {} ({})".format(
                    self.wrap(name),
                    self.wrap(blueprint.table),
                    ", ".join(self.wrap(c) for c in index["columns"]),
                )
            )

        # A unique() modifier on a column in an ALTER cannot go inline.
        if blueprint.mode == "alter":
            for column in blueprint.columns:
                if column.is_unique:
                    statements.append(
                        "CREATE UNIQUE INDEX {} ON {} ({})".format(
                            self.wrap("{}_{}_unique".format(blueprint.table, column.name)),
                            self.wrap(blueprint.table),
                            self.wrap(column.name),
                        )
                    )

        return statements

    def column_sql(self, column, for_alter=False):
        type_sql = self.type_sql(column)
        parts = [self.wrap(column.name), type_sql]

        if column.auto_increment:
            parts = self.auto_increment_sql(column)
        else:
            if column.is_unsigned and self.driver == "mysql":
                parts.append("UNSIGNED")

            parts.append("NULL" if column.is_nullable else "NOT NULL")

            if column.default_value is not _NO_DEFAULT:
                parts.append("DEFAULT " + self.default_sql(column.default_value))

            # In a CREATE, UNIQUE can go inline; in an ALTER it becomes a
            # separate CREATE UNIQUE INDEX, handled above.
            if column.is_unique and not for_alter:
                parts.append("UNIQUE")

        return " ".join(parts)

    def auto_increment_sql(self, column):
        if self.driver == "sqlite":
            return [self.wrap(column.name), "INTEGER", "PRIMARY KEY", "AUTOINCREMENT"]

        if self.driver == "mysql":
            return [
                self.wrap(column.name),
                "BIGINT UNSIGNED",
                "NOT NULL",
                "AUTO_INCREMENT",
                "PRIMARY KEY",
            ]

        return [self.wrap(column.name), "BIGSERIAL", "PRIMARY KEY"]

    def type_sql(self, column):
        template = self.TYPES[self.driver].get(column.type_name, "TEXT")

        return template.format(
            length=column.options.get("length", 255),
            precision=column.options.get("precision", 8),
            scale=column.options.get("scale", 2),
        )

    def default_sql(self, value):
        if value is _CURRENT_TIMESTAMP:
            return "CURRENT_TIMESTAMP"

        if value is None:
            return "NULL"

        if isinstance(value, bool):
            if self.driver == "pgsql":
                return "TRUE" if value else "FALSE"

            return "1" if value else "0"

        if isinstance(value, (int, float)):
            return str(value)

        return "'{}'".format(str(value).replace("'", "''"))

    def foreign_sql(self, column):
        foreign = column.foreign
        clause = "FOREIGN KEY ({}) REFERENCES {} ({})".format(
            self.wrap(column.name),
            self.wrap(foreign["table"]),
            self.wrap(foreign["column"]),
        )

        if foreign["on_delete"]:
            clause += " ON DELETE " + foreign["on_delete"].upper()

        if foreign["on_update"]:
            clause += " ON UPDATE " + foreign["on_update"].upper()

        return clause


class SchemaBuilder(AliasMixin):
    """`Schema` — the object migrations talk to."""

    def __init__(self, connection=None):
        self._connection = connection

    def connection(self):
        if self._connection is not None:
            return self._connection

        from ..facades import DB

        return DB.connection()

    def use(self, connection):
        """Bind this builder to a connection, as the migrator does."""
        return SchemaBuilder(connection)

    # -- creating ---------------------------------------------------------

    def create(self, table, callback=None):
        blueprint = Blueprint(table, "create")

        if callback is None:
            # Supports `with Schema.create('posts') as table:`
            return _BlueprintContext(self, blueprint)

        callback(blueprint)
        self._run(blueprint)

        return self

    def table(self, table, callback=None):
        blueprint = Blueprint(table, "alter")

        if callback is None:
            return _BlueprintContext(self, blueprint)

        callback(blueprint)
        self._run(blueprint)

        return self

    def _run(self, blueprint):
        connection = self.connection()
        grammar = Grammar(connection)

        statements = (
            grammar.compile_create(blueprint)
            if blueprint.mode == "create"
            else grammar.compile_alter(blueprint)
        )

        for statement in statements:
            connection.statement(statement)

        return self

    # -- dropping ---------------------------------------------------------

    def drop(self, table):
        self.connection().statement(
            "DROP TABLE {}".format(self.connection().wrap(_identifier(table, "table")))
        )

        return self

    def drop_if_exists(self, table):
        self.connection().statement(
            "DROP TABLE IF EXISTS {}".format(self.connection().wrap(_identifier(table, "table")))
        )

        return self

    def rename(self, old, new):
        connection = self.connection()
        connection.statement(
            "ALTER TABLE {} RENAME TO {}".format(
                connection.wrap(_identifier(old, "table")),
                connection.wrap(_identifier(new, "table")),
            )
        )

        return self

    # -- inspecting -------------------------------------------------------

    def has_table(self, table):
        connection = self.connection()
        driver = Grammar._normalise(connection.driver)

        if driver == "sqlite":
            row = connection.select_one(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?", [table]
            )
        elif driver == "mysql":
            row = connection.select_one(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = DATABASE() AND table_name = ?",
                [table],
            )
        else:
            row = connection.select_one(
                "SELECT tablename FROM pg_catalog.pg_tables "
                "WHERE schemaname = 'public' AND tablename = ?",
                [table],
            )

        return row is not None

    def has_column(self, table, column):
        return column in self.column_listing(table)

    def column_listing(self, table):
        connection = self.connection()
        driver = Grammar._normalise(connection.driver)

        if driver == "sqlite":
            rows = connection.select(
                "PRAGMA table_info({})".format(connection.wrap(_identifier(table, "table")))
            )

            return [row["name"] for row in rows]

        if driver == "mysql":
            rows = connection.select(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = DATABASE() AND table_name = ?",
                [table],
            )
        else:
            rows = connection.select(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = ?",
                [table],
            )

        return [list(row.values())[0] for row in rows]


class _BlueprintContext:
    """Lets a Blueprint be used as a context manager.

        with Schema.create('posts') as table:
            table.id()
    """

    def __init__(self, builder, blueprint):
        self._builder = builder
        self._blueprint = blueprint

    def __enter__(self):
        return self._blueprint

    def __exit__(self, exc_type, exc_value, traceback):
        # A failed body means the migration is wrong; running a half-built
        # CREATE TABLE on top of that would only make the mess harder to undo.
        if exc_type is None:
            self._builder._run(self._blueprint)

        return False


#: The facade migrations import.
Schema = SchemaBuilder()
