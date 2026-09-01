"""The make: generators."""

import os
from datetime import datetime

from ..command import Command


class _Generator(Command):
    """Shared plumbing: resolve a name, render a stub, report what was made."""

    stub_name = ""

    def target_path(self, name):
        raise NotImplementedError

    def replacements(self, name):
        return {"name": name}

    def stub_to_use(self):
        return self.stub_name

    def handle(self):
        raw = self.argument(0)

        if not raw:
            self.error("  Please give it a name.")
            self.line("")
            self.line("      " + self.usage)
            self.line("")

            return 1

        name = self.studly(raw)
        path = self.target_path(name)

        created = self.write_file(
            path,
            self.render_stub(self.stub_to_use(), self.replacements(name)),
            force=self.flag("force"),
        )

        if not created:
            self.line("  Use --force to overwrite it.")

            return 1

        self.line("")
        self.success("  Created " + self.relative(path))
        self.line("")

        self.after(name, path)

        return 0

    def after(self, name, path):
        """Hook for generators that create more than one file."""


class MakeControllerCommand(_Generator):
    name = "make:controller"

    description = "Create a controller in app/Http/Controllers"

    usage = "bazimya make:controller <Name> [--resource] [--api] [--model=Post] [--force]"

    stub_name = "controller"

    def stub_to_use(self):
        if self.flag("api"):
            return "controller.api"

        return "controller.resource" if self.flag("resource") else "controller"

    def target_path(self, name):
        return self.application().app_path("Http", "Controllers", name + ".py")

    def replacements(self, name):
        from ...support.strings import plural, snake

        model = self.option("model")
        model = self.studly(model) if model else name.replace("Controller", "") or "Item"
        resource = plural(snake(model))

        return {
            "name": name,
            "model": model,
            "variable": snake(model),
            "plural": resource,
            "views": resource,
        }


class MakeModelCommand(_Generator):
    name = "make:model"

    description = "Create a model in app/Models"

    usage = "bazimya make:model <Name> [--migration] [--controller] [--force]"

    stub_name = "model"

    def target_path(self, name):
        return self.application().app_path("Models", name + ".py")

    def replacements(self, name):
        from ...support.strings import plural, snake

        return {"name": name, "table": plural(snake(name))}

    def after(self, name, path):
        if self.flag("migration") or self.flag("m"):
            from ...support.strings import plural, snake

            table = plural(snake(name))
            self._delegate(
                MakeMigrationCommand,
                ["create_{}_table".format(table)],
                {"create": table},
            )

        if self.flag("controller") or self.flag("c"):
            self._delegate(
                MakeControllerCommand,
                [name + "Controller"],
                {"resource": True, "model": name},
            )

    def _delegate(self, command_class, args, options):
        command = command_class(self.app, self.output)
        command.set_input(args, options)
        command.handle()


class MakeMigrationCommand(Command):
    name = "make:migration"

    description = "Create a migration in database/migrations"

    usage = "bazimya make:migration <name> [--create=table] [--table=table]"

    def handle(self):
        raw = self.argument(0)

        if not raw:
            self.error("  Please name the migration, e.g. create_posts_table.")

            return 1

        name = self.snake(raw)
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        filename = "{}_{}.py".format(timestamp, name)
        path = self.application().migrations_path(filename)

        create = self.option("create")
        table = self.option("table")

        if create:
            stub, target = "migration.create", create
        elif table:
            stub, target = "migration.table", table
        else:
            # Infer from the conventional name, which is what people expect
            # from `make:migration create_posts_table`.
            guessed = self._guess(name)
            stub, target = guessed if guessed else ("migration", "")

        contents = self.render_stub(
            stub, {"class": self.studly(name), "table": target, "name": name}
        )

        if not self.write_file(path, contents, force=self.flag("force")):
            return 1

        self.line("")
        self.success("  Created " + self.relative(path))
        self.line("")

        return 0

    @staticmethod
    def _guess(name):
        if name.startswith("create_") and name.endswith("_table"):
            return "migration.create", name[len("create_") : -len("_table")]

        for prefix in ("add_", "update_", "change_", "drop_"):
            if name.startswith(prefix) and "_to_" in name:
                table = name.split("_to_", 1)[1]

                if table.endswith("_table"):
                    table = table[: -len("_table")]

                return "migration.table", table

        return None


class MakeMiddlewareCommand(_Generator):
    name = "make:middleware"

    description = "Create middleware in app/Http/Middleware"

    usage = "bazimya make:middleware <Name> [--force]"

    stub_name = "middleware"

    def target_path(self, name):
        return self.application().app_path("Http", "Middleware", name + ".py")

    def after(self, name, path):
        from ...support.strings import snake

        alias = snake(name).replace("_", ".")

        self.comment("  Register it in app/Http/Kernel.py:")
        self.line("")
        self.line("      middleware_aliases = {")
        self.line("          '{}': {},".format(alias, name))
        self.line("      }")
        self.line("")


class MakeProviderCommand(_Generator):
    name = "make:provider"

    description = "Create a service provider in app/Providers"

    usage = "bazimya make:provider <Name> [--force]"

    stub_name = "provider"

    def target_path(self, name):
        return self.application().app_path("Providers", name + ".py")

    def after(self, name, path):
        self.comment("  Add it to the providers list in config/app.py:")
        self.line("")
        self.line("      'app.Providers.{}.{}',".format(name, name))
        self.line("")


class MakeSeederCommand(_Generator):
    name = "make:seeder"

    description = "Create a seeder in database/seeders"

    usage = "bazimya make:seeder <Name> [--force]"

    stub_name = "seeder"

    def target_path(self, name):
        return self.application().database_path("seeders", name + ".py")


class MakeExtensionCommand(Command):
    name = "make:extension"

    description = "Scaffold an extension in extensions/"

    usage = "bazimya make:extension <Name> [--prefix=blog] [--force]"

    def handle(self):
        raw = self.argument(0)

        if not raw:
            self.error("  Please give the extension a name.")
            self.line("")
            self.line("      " + self.usage)

            return 1

        name = self.studly(raw)
        namespace = name.lower()
        prefix = str(self.option("prefix", namespace) or namespace).strip("/")
        force = self.flag("force")

        directory = self.application().extensions_path(name)

        if os.path.isdir(directory) and not force:
            self.error("  Extension [{}] already exists.".format(name))
            self.line("  Use --force to overwrite it.")

            return 1

        replacements = {
            "name": name,
            "namespace": namespace,
            "prefix": prefix,
            "description": str(self.option("description", "The {} extension.".format(name))),
        }

        files = [
            (os.path.join(directory, "__init__.py"), "extension"),
            (os.path.join(directory, "views", "index.baz.html"), "extension.view"),
        ]

        written = []

        for path, stub in files:
            if self.write_file(path, self.render_stub(stub, replacements), force):
                written.append(path)

        if not written:
            return 1

        migrations = os.path.join(directory, "migrations")
        os.makedirs(migrations, exist_ok=True)

        with open(os.path.join(migrations, ".gitkeep"), "w", encoding="utf-8") as handle:
            handle.write("# Migrations here are run by `bazimya migrate`.\n")

        self.line("")
        self.success("  Extension [{}] created.".format(name))
        self.line("")

        for path in written:
            self.line("    " + self.relative(path))

        self.line("")
        self.comment("  Next:")
        self.line("")
        self.line("      bazimya extension:list")
        self.line("      bazimya serve        # then open /{}".format(prefix))
        self.line("")

        return 0


class MakeRequestCommand(_Generator):
    name = "make:request"

    description = "Create a form request in app/Http/Requests"

    usage = "bazimya make:request <Name> [--force]"

    stub_name = "request"

    def target_path(self, name):
        return self.application().app_path("Http", "Requests", name + ".py")


class MakeRuleCommand(_Generator):
    name = "make:rule"

    description = "Create a validation rule in app/Rules"

    usage = "bazimya make:rule <Name> [--force]"

    stub_name = "rule"

    def target_path(self, name):
        return self.application().app_path("Rules", name + ".py")


class MakeCommandCommand(_Generator):
    name = "make:command"

    description = "Create a console command in app/Console/Commands"

    usage = "bazimya make:command <Name> [--command=my:name] [--force]"

    stub_name = "command"

    def target_path(self, name):
        return self.application().app_path("Console", "Commands", name + ".py")

    def replacements(self, name):
        from ...support.strings import kebab

        default = kebab(name.replace("Command", "")) or "my:command"

        return {"name": name, "signature": str(self.option("command", default))}

    def after(self, name, path):
        self.comment("  Add it to app/Console/Kernel.py:")
        self.line("")
        self.line("      from app.Console.Commands import {}".format(name))
        self.line("")
        self.line("      commands = [{}]".format(name))
        self.line("")


class MakeNotificationCommand(_Generator):
    name = "make:notification"

    description = "Create a notification in app/Notifications"

    usage = "bazimya make:notification <Name> [--force]"

    stub_name = "notification"

    def target_path(self, name):
        return self.application().app_path("Notifications", name + ".py")


class MakeComponentCommand(Command):
    name = "make:component"

    description = "Create a view component and its template"

    usage = "bazimya make:component <Name> [--view-only] [--force]"

    def handle(self):
        raw = self.argument(0)

        if not raw:
            self.error("  Please give the component a name.")
            self.line("")
            self.line("      " + self.usage)

            return 1

        from ...support.strings import kebab

        name = self.studly(raw)
        tag = kebab(name)
        force = self.flag("force")
        application = self.application()

        written = []

        # An anonymous component is just a template; --view-only skips the
        # class, which is the right shape for markup with no logic.
        if not self.flag("view-only"):
            path = application.app_path("View", "Components", name + ".py")

            if self.write_file(path, self.render_stub("component", {"name": name, "tag": tag}), force):
                written.append(path)

        template = application.views_path("components", tag + ".baz.html")

        if self.write_file(template, self.render_stub("component.view", {"tag": tag}), force):
            written.append(template)

        if not written:
            return 1

        self.line("")
        self.success("  Component <x-{}> created.".format(tag))
        self.line("")

        for path in written:
            self.line("    " + self.relative(path))

        self.line("")
        self.comment("  Use it in a template:")
        self.line("")
        self.line("      <x-{}>content</x-{}>".format(tag, tag))
        self.line("")

        return 0
