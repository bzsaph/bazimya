"""The base command.

Every CLI command subclasses this and implements handle(). Input arrives
already split into positional arguments and --options.
"""

import os

from .output import Output


class Command:
    #: The name typed on the command line, e.g. "make:controller".
    name = ""

    description = ""

    usage = ""

    #: False for commands that run outside a project, like `new`.
    needs_application = True

    def __init__(self, application=None, output=None):
        self.app = application
        self.output = output or Output()
        self.args = []
        self.options = {}

    def set_input(self, args, options):
        self.args = list(args)
        self.options = dict(options)

        return self

    def set_application(self, application):
        self.app = application

        return self

    def handle(self):
        raise NotImplementedError(
            "{} must implement handle().".format(type(self).__name__)
        )

    # -- input ------------------------------------------------------------

    def argument(self, index, default=None):
        return self.args[index] if index < len(self.args) else default

    def option(self, key, default=None):
        value = self.options.get(key, default)

        return default if value is True and not isinstance(default, bool) else value

    def flag(self, key):
        return bool(self.options.get(key, False))

    def application(self):
        if self.app is None:
            raise RuntimeError(
                "This command must be run from inside a Bazimya project.\n"
                "Create one with:  bazimya new my-app"
            )

        return self.app

    # -- output -----------------------------------------------------------

    def line(self, message=""):
        self.output.line(message)

    def info(self, message):
        self.output.info(message)

    def success(self, message):
        self.output.success(message)

    def warn(self, message):
        self.output.warn(message)

    def error(self, message):
        self.output.error(message)

    def comment(self, message):
        self.output.comment(message)

    def table(self, headers, rows):
        self.output.table(headers, rows)

    def confirm(self, question, default=False):
        return self.output.confirm(question, default)

    def ask(self, question, default=None):
        return self.output.ask(question, default)

    # -- filesystem -------------------------------------------------------

    def framework_path(self, *parts):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(root, *parts) if parts else root

    def stub(self, name):
        path = self.framework_path("stubs", name + ".stub")

        if not os.path.isfile(path):
            raise FileNotFoundError("Stub [{}] was not found at {}".format(name, path))

        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()

    def render_stub(self, name, replacements=None):
        contents = self.stub(name)

        for key, value in (replacements or {}).items():
            contents = contents.replace("{{" + key + "}}", str(value))

        return contents

    def write_file(self, path, contents, force=False):
        if os.path.exists(path) and not force:
            self.error("  Already exists: " + self.relative(path))

            return False

        directory = os.path.dirname(path)

        if directory:
            os.makedirs(directory, exist_ok=True)

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(contents)

        return True

    def relative(self, path):
        base = self.app.base_path if self.app else os.getcwd()

        try:
            return os.path.relpath(path, base)
        except ValueError:
            return path

    # -- helpers ----------------------------------------------------------

    def migrator(self):
        """A migrator that sees the app's migrations and every extension's."""
        from ..database.migration import Migrator

        application = self.application()

        return Migrator(application.make("db"), application.migration_paths())

    @staticmethod
    def studly(value):
        from ..support.strings import studly

        return studly(value)

    @staticmethod
    def snake(value):
        from ..support.strings import snake

        return snake(value)
