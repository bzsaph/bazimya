"""Migration commands."""

import os

from ..command import Command


class MigrateCommand(Command):
    name = "migrate"

    description = "Run the pending database migrations"

    usage = "bazimya migrate [--pretend] [--seed]"

    def handle(self):
        migrator = self.migrator()
        pending = migrator.pending()

        self.line("")

        if not pending:
            self.comment("  Nothing to migrate.")
            self.line("")

            return 0

        for name, _ in pending:
            self.line("  running   " + name)

        applied = migrator.run(pretend=self.flag("pretend"))

        self.line("")

        if self.flag("pretend"):
            self.comment("  --pretend: nothing was actually run.")
        else:
            self.success(
                "  Migrated {} migration{}.".format(len(applied), "" if len(applied) == 1 else "s")
            )

        self.line("")

        if self.flag("seed") and not self.flag("pretend"):
            return DbSeedCommand(self.app, self.output).set_input([], {}).handle()

        return 0


class MigrateRollbackCommand(Command):
    name = "migrate:rollback"

    description = "Roll back the last batch of migrations"

    usage = "bazimya migrate:rollback [--step=1]"

    def handle(self):
        steps = int(self.option("step", 1) or 1)
        rolled_back = self.migrator().rollback(steps)

        self.line("")

        if not rolled_back:
            self.comment("  Nothing to roll back.")
            self.line("")

            return 0

        for name in rolled_back:
            self.line("  rolled back   " + name)

        self.line("")
        self.success(
            "  Rolled back {} migration{}.".format(
                len(rolled_back), "" if len(rolled_back) == 1 else "s"
            )
        )
        self.line("")

        return 0


class MigrateFreshCommand(Command):
    name = "migrate:fresh"

    description = "Roll everything back and migrate again"

    usage = "bazimya migrate:fresh [--seed] [--force]"

    def handle(self):
        application = self.application()

        # This destroys data. In production it needs saying out loud.
        if application.is_production() and not self.flag("force"):
            self.line("")
            self.warn("  APP_ENV is production. migrate:fresh will drop every table.")

            if not self.confirm("  Really do this?"):
                self.line("  Cancelled.")

                return 1

        migrator = self.migrator()

        self.line("")
        self.comment("  Rolling everything back...")

        rolled_back = migrator.reset()

        for name in rolled_back:
            self.line("  rolled back   " + name)

        applied = migrator.run()

        for name in applied:
            self.line("  migrated      " + name)

        self.line("")
        self.success("  Database refreshed.")
        self.line("")

        if self.flag("seed"):
            return DbSeedCommand(self.app, self.output).set_input([], {}).handle()

        return 0


class MigrateStatusCommand(Command):
    name = "migrate:status"

    description = "Show which migrations have run"

    usage = "bazimya migrate:status"

    def handle(self):
        status = self.migrator().status()

        self.line("")

        if not status:
            self.comment("  No migrations found.")
            self.line("")

            return 0

        rows = [
            ["Yes" if entry["ran"] else "No", entry["migration"], self.relative(entry["path"])]
            for entry in status
        ]

        self.table(["Ran", "Migration", "Path"], rows)
        self.line("")

        pending = sum(1 for entry in status if not entry["ran"])

        if pending:
            self.comment("  {} pending. Run: bazimya migrate".format(pending))
        else:
            self.success("  Everything is migrated.")

        self.line("")

        return 0


class DbSeedCommand(Command):
    name = "db:seed"

    description = "Run the database seeders"

    usage = "bazimya db:seed [--class=DatabaseSeeder]"

    def handle(self):
        import importlib.util
        import inspect

        application = self.application()
        target = str(self.option("class", "DatabaseSeeder"))
        path = application.database_path("seeders", target + ".py")

        self.line("")

        if not os.path.isfile(path):
            self.error("  Seeder [{}] was not found at {}".format(target, self.relative(path)))
            self.line("")
            self.line("  Create one with:  bazimya make:seeder " + target)
            self.line("")

            return 1

        spec = importlib.util.spec_from_file_location("bazimya_seeder_" + target, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        seeder = getattr(module, target, None)

        if seeder is None:
            self.error("  {} does not define a class called {}.".format(self.relative(path), target))

            return 1

        instance = seeder() if inspect.isclass(seeder) else seeder

        self.comment("  Seeding: " + target)
        instance.run()

        self.line("")
        self.success("  Seeding complete.")
        self.line("")

        return 0
