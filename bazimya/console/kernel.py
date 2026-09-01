"""The CLI kernel: parse argv, find the command, run it."""

import os
import sys
import traceback

from .output import Output


class Kernel:
    def __init__(self):
        self.output = Output()
        self._application = None
        self._resolved = False

    # -- the command table ------------------------------------------------

    def commands(self):
        from .commands.build import BuildCommand
        from .commands.doctor import DoctorCommand
        from .commands.inspect import (
            CacheClearCommand,
            ExtensionListCommand,
            RouteListCommand,
            TinkerCommand,
            ViewCacheCommand,
        )
        from .commands.make import (
            MakeCommandCommand,
            MakeComponentCommand,
            MakeControllerCommand,
            MakeExtensionCommand,
            MakeMiddlewareCommand,
            MakeMigrationCommand,
            MakeModelCommand,
            MakeNotificationCommand,
            MakeProviderCommand,
            MakeRequestCommand,
            MakeRuleCommand,
            MakeSeederCommand,
        )
        from .commands.migrate import (
            DbSeedCommand,
            MigrateCommand,
            MigrateFreshCommand,
            MigrateRollbackCommand,
            MigrateStatusCommand,
        )
        from .commands.new import NewCommand
        from .commands.serve import ServeCommand

        return [
            NewCommand,
            ServeCommand,
            BuildCommand,
            DoctorCommand,
            TinkerCommand,
            MakeControllerCommand,
            MakeModelCommand,
            MakeMigrationCommand,
            MakeMiddlewareCommand,
            MakeProviderCommand,
            MakeRequestCommand,
            MakeRuleCommand,
            MakeSeederCommand,
            MakeNotificationCommand,
            MakeComponentCommand,
            MakeCommandCommand,
            MakeExtensionCommand,
            MigrateCommand,
            MigrateRollbackCommand,
            MigrateFreshCommand,
            MigrateStatusCommand,
            DbSeedCommand,
            RouteListCommand,
            ExtensionListCommand,
            CacheClearCommand,
            ViewCacheCommand,
        ]

    # -- running ----------------------------------------------------------

    def run(self, argv):
        name = argv[1] if len(argv) > 1 else None

        if name is None or name in ("list", "help", "--help", "-h"):
            self.render_help()

            return 0

        if name in ("--version", "-V", "version"):
            from ..foundation.application import VERSION

            self.output.line("Bazimya " + VERSION)

            return 0

        args, options = self.parse(argv[2:])

        command_class = self.resolve(name)

        if command_class is None:
            handled = self.run_extension_command(name, args, options)

            if handled is not None:
                return handled

            self.output.error('Unknown command "{}".'.format(name))
            self.suggest(name)

            return 1

        application = self.application()

        if application is None and command_class.needs_application:
            self.output.error("This does not look like a Bazimya project.")
            self.output.line("")
            self.output.line("  Run this from a project directory, or create one:")
            self.output.line("")
            self.output.line("      bazimya new my-app")
            self.output.line("")

            return 1

        command = command_class(application, self.output)
        command.set_input(args, options)

        try:
            return int(command.handle() or 0)
        except KeyboardInterrupt:
            self.output.line("")

            return 130
        except Exception as error:  # noqa: BLE001 — the CLI's last line
            return self.report(error)

    def resolve(self, name):
        for command_class in self.commands():
            if command_class.name == name:
                return command_class

        for command_class in self.application_commands():
            if command_class.name == name:
                return command_class

        return None

    def application_commands(self):
        """Command classes listed in app/Console/Kernel.py.

        Best effort: `bazimya list` and every built-in must still work when the
        project's own console kernel is broken.
        """
        application = self.application()

        if application is None:
            return []

        try:
            classes, _ = application.console_commands()

            return classes
        except Exception:  # noqa: BLE001
            return []

    def console_route_commands(self):
        """Closure commands registered in routes/console.py."""
        application = self.application()

        if application is None:
            return []

        try:
            _, closures = application.console_commands()

            return closures
        except Exception:  # noqa: BLE001
            return []

    def report(self, error):
        self.output.error("  " + str(error))

        if os.environ.get("BAZIMYA_DEBUG"):
            self.output.line("")
            self.output.line(traceback.format_exc())
        else:
            self.output.line("")
            self.output.comment("  Run again with BAZIMYA_DEBUG=1 for the traceback.")

        return 1

    # -- extension commands -----------------------------------------------

    def run_extension_command(self, name, args, options):
        """Run a command declared by an extension, or return None."""
        application = self.application()

        if application is None:
            return None

        try:
            application.boot()
            command = application.make("extensions").find_command(name)

            if command is None:
                from ..console.registry import Console

                application.load_console_routes()
                command = Console.find(name)
        except Exception as error:  # noqa: BLE001
            return self.report(error)

        if command is None:
            return None

        try:
            result = command["handler"](args, options)
        except Exception as error:  # noqa: BLE001
            return self.report(error)

        if isinstance(result, str):
            self.output.line(result)

            return 0

        return int(result) if isinstance(result, int) and not isinstance(result, bool) else 0

    # -- the project ------------------------------------------------------

    def application(self):
        """Find and build the application, walking up from the cwd.

        Memoised, including the "no project here" answer — several code paths
        ask, and walking the tree twice would be wasted work.
        """
        if self._resolved:
            return self._application

        self._resolved = True
        self._application = self._locate()

        return self._application

    def _locate(self):
        directory = os.getcwd()

        while True:
            if self._looks_like_project(directory):
                sys.path.insert(0, directory)

                from ..foundation.application import Application

                return Application(directory)

            parent = os.path.dirname(directory)

            if parent == directory:
                return None

            directory = parent

    @staticmethod
    def _looks_like_project(directory):
        return os.path.isdir(os.path.join(directory, "routes")) and (
            os.path.isfile(os.path.join(directory, "bazimya"))
            or os.path.isdir(os.path.join(directory, "bootstrap"))
        )

    # -- input parsing ----------------------------------------------------

    @staticmethod
    def parse(tokens):
        """Split tokens into positional arguments and --options.

        Supports --flag, --key=value, --key value, and short -m style flags.
        """
        args = []
        options = {}
        index = 0

        while index < len(tokens):
            token = tokens[index]

            if token == "--":
                args.extend(tokens[index + 1 :])
                break

            if token.startswith("--"):
                body = token[2:]

                if "=" in body:
                    key, _, value = body.partition("=")
                    options[key] = value
                elif index + 1 < len(tokens) and not tokens[index + 1].startswith("-"):
                    # --port 8000 as well as --port=8000.
                    options[body] = tokens[index + 1]
                    index += 1
                else:
                    options[body] = True
            elif token.startswith("-") and len(token) > 1:
                for letter in token[1:]:
                    options[letter] = True
            else:
                args.append(token)

            index += 1

        return args, options

    # -- help -------------------------------------------------------------

    def suggest(self, name):
        import difflib

        available = [c.name for c in self.commands()]
        close = difflib.get_close_matches(name, available, n=3, cutoff=0.5)

        close.extend(c for c in available if name in c and c not in close)

        if close:
            self.output.line("")
            self.output.line("Did you mean:")

            for candidate in close[:5]:
                self.output.line("  " + candidate)

        self.output.line("")
        self.output.line('Run "bazimya list" to see every command.')

    def render_help(self):
        from ..foundation.application import VERSION

        out = self.output

        out.line("")
        out.line("  " + out.bold("Bazimya") + " " + VERSION)
        out.line("  A Python web framework with no dependencies.")
        out.line("")
        out.line("  " + out.bold("USAGE"))
        out.line("      bazimya <command> [arguments] [--options]")
        out.line("")
        out.line("  " + out.bold("COMMANDS"))

        groups = {}

        for command_class in self.commands():
            group = command_class.name.split(":")[0] if ":" in command_class.name else "general"
            groups.setdefault(group, []).append(
                (command_class.name, command_class.description)
            )

        for command_class in self.application_commands():
            group = command_class.name.split(":")[0] if ":" in command_class.name else "app"
            groups.setdefault(group, []).append(
                (command_class.name, command_class.description)
            )

        for command in self.console_route_commands():
            group = command["name"].split(":")[0] if ":" in command["name"] else "app"
            groups.setdefault(group, []).append((command["name"], command["description"]))

        for group, entries in self.extension_command_groups().items():
            groups.setdefault(group, []).extend(entries)

        for group in sorted(groups, key=lambda g: (g != "general", g)):
            entries = groups[group]

            out.line("")
            out.comment("    " + group)

            width = max(len(name) for name, _ in entries)

            for name, description in entries:
                out.line("      " + name.ljust(width + 4) + description)

        out.line("")

    def extension_command_groups(self):
        """Commands contributed by extensions. Best effort: help must render
        even when a project is broken."""
        try:
            application = self.application()

            if application is None:
                return {}

            application.boot()

            groups = {}

            for command in application.make("extensions").commands():
                group = (
                    command["name"].split(":")[0]
                    if ":" in command["name"]
                    else command["extension"].lower()
                )
                groups.setdefault(group, []).append(
                    (command["name"], command["description"])
                )

            return groups
        except Exception:  # noqa: BLE001
            return {}


def main(argv=None):
    """Entry point for `python -m bazimya` and the console script."""
    return Kernel().run(list(argv if argv is not None else sys.argv))
