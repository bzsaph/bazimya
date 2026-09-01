"""Migrations and the migrator.

A migration file defines a Migration subclass:

    from bazimya import Migration, Schema

    class CreatePostsTable(Migration):
        def up(self):
            with Schema.create('posts') as table:
                table.id()
                table.string('title')
                table.timestamps()

        def down(self):
            Schema.drop_if_exists('posts')

Files are found across several directories — the application's own
database/migrations, plus a migrations/ folder inside any extension that ships
one — and ordered by filename, which is why names start with a timestamp.
"""

import importlib.util
import inspect
import os


class Migration:
    """Base class. Override up() and down()."""

    #: Set to False for a migration that cannot run inside a transaction.
    transactional = True

    def __init__(self, connection=None):
        self.connection = connection

    def up(self):
        raise NotImplementedError(
            "{} must implement up().".format(type(self).__name__)
        )

    def down(self):
        raise NotImplementedError(
            "{} must implement down(). Make it a no-op if the change really "
            "cannot be reversed, so rollbacks do not stop here.".format(type(self).__name__)
        )

    # -- helpers ----------------------------------------------------------

    @property
    def schema(self):
        from .schema import SchemaBuilder

        return SchemaBuilder(self.connection) if self.connection else None

    def execute(self, sql, bindings=None):
        return self.connection.statement(sql, bindings)

    def select(self, sql, bindings=None):
        return self.connection.select(sql, bindings)


class DuplicateMigration(RuntimeError):
    pass


class Migrator:
    def __init__(self, connection, paths=None):
        self.connection = connection
        self.paths = []

        for path in _as_list(paths):
            self.add_path(path)

    def add_path(self, path):
        if path and path not in self.paths:
            self.paths.append(path)

        return self

    # -- the migrations table ---------------------------------------------

    def ensure_table(self):
        from .schema import SchemaBuilder

        schema = SchemaBuilder(self.connection)

        if schema.has_table("migrations"):
            return

        with schema.create("migrations") as table:
            table.id()
            table.string("migration")
            table.integer("batch")

    def ran(self):
        self.ensure_table()

        return [
            row["migration"]
            for row in self.connection.table("migrations").order_by("id").get()
        ]

    # -- discovery --------------------------------------------------------

    def files(self):
        """Every migration file, keyed by name, ordered by name.

        Two directories offering the same filename is a genuine conflict: the
        migrations table records only the name, so one would shadow the other
        and rollbacks would run the wrong file.
        """
        found = {}

        for path in self.paths:
            if not os.path.isdir(path):
                continue

            for entry in sorted(os.listdir(path)):
                if not entry.endswith(".py") or entry.startswith("_"):
                    continue

                name = entry[:-3]

                if name in found:
                    raise DuplicateMigration(
                        "Two migrations are named [{}]:\n  {}\n  {}\n"
                        "Rename one — the migrations table records the name only.".format(
                            name, found[name], os.path.join(path, entry)
                        )
                    )

                found[name] = os.path.join(path, entry)

        return dict(sorted(found.items()))

    def pending(self):
        ran = set(self.ran())

        return [(name, path) for name, path in self.files().items() if name not in ran]

    # -- running ----------------------------------------------------------

    def run(self, pretend=False):
        pending = self.pending()

        if not pending:
            return []

        batch = self.next_batch()
        applied = []

        for name, path in pending:
            migration = self.resolve(path, name)

            if pretend:
                applied.append(name)
                continue

            self._run_migration(migration, "up")

            self.connection.table("migrations").insert(
                {"migration": name, "batch": batch}
            )

            applied.append(name)

        return applied

    def rollback(self, steps=1):
        self.ensure_table()

        rolled_back = []
        files = self.files()

        for _ in range(max(1, steps)):
            batch = self.connection.table("migrations").order_by("batch", "desc").value("batch")

            if not batch:
                break

            rows = (
                self.connection.table("migrations")
                .where("batch", batch)
                .order_by("id", "desc")
                .get()
            )

            for row in rows:
                name = row["migration"]
                path = files.get(name)

                if path is None:
                    raise FileNotFoundError(
                        "The migration file for [{}] is missing. Looked in:\n  {}".format(
                            name, "\n  ".join(self.paths) or "(no paths registered)"
                        )
                    )

                self._run_migration(self.resolve(path, name), "down")

                self.connection.table("migrations").where("migration", name).delete()
                rolled_back.append(name)

        return rolled_back

    def reset(self):
        return self.rollback(steps=10_000)

    def _run_migration(self, migration, direction):
        method = getattr(migration, direction)

        # SQLite cannot roll back most DDL, so a transaction buys little there
        # and can deadlock a second connection; the other drivers benefit.
        use_transaction = (
            migration.transactional and self.connection.driver not in ("sqlite",)
        )

        if not use_transaction:
            method()

            return

        self.connection.transaction(method)

    def resolve(self, path, name):
        """Import a migration file and instantiate the Migration it defines."""
        module_name = "bazimya_migration_" + name.replace("-", "_").replace(".", "_")
        spec = importlib.util.spec_from_file_location(module_name, path)

        if spec is None or spec.loader is None:
            raise ImportError("Could not load the migration at {}".format(path))

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            # Subclasses only — the imported Migration base is in the module
            # namespace too, and instantiating it would do nothing.
            if issubclass(candidate, Migration) and candidate is not Migration:
                if candidate.__module__ != module_name:
                    continue

                return candidate(self.connection)

        raise ImportError(
            "{} does not define a Migration subclass.\n\n"
            "    from bazimya import Migration, Schema\n\n"
            "    class {}(Migration):\n"
            "        def up(self): ...\n"
            "        def down(self): ...".format(path, _class_name_for(name))
        )

    def next_batch(self):
        current = self.connection.table("migrations").order_by("batch", "desc").value("batch")

        return int(current or 0) + 1

    def status(self):
        """Every migration and whether it has run — for `migrate:status`."""
        ran = set(self.ran())

        return [
            {"migration": name, "ran": name in ran, "path": path}
            for name, path in self.files().items()
        ]


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return list(value)

    return [value]


def _class_name_for(name):
    from ..support.strings import studly

    # 2026_01_01_000000_create_posts_table -> CreatePostsTable
    parts = name.split("_")

    while parts and parts[0].isdigit():
        parts.pop(0)

    return studly("_".join(parts)) or "Migration"
