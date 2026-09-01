"""bazimya doctor — why does it work here and not there?

Runs locally and on a server, and reports the handful of things that actually
differ between the two.
"""

import os
import sys

from ..command import Command


class DoctorCommand(Command):
    name = "doctor"

    description = "Check the environment for anything that will bite in production"

    usage = "bazimya doctor"

    needs_application = False

    def __init__(self, application=None, output=None):
        super().__init__(application, output)
        self.problems = 0
        self.cautions = 0

    def handle(self):
        from ...foundation.application import VERSION

        self.line("")
        self.info("  Bazimya {} — environment check".format(VERSION))

        self._check_python()

        if self.app is None:
            self._heading("Project")
            self.line("    Not inside a Bazimya project; project checks skipped.")
        else:
            self._check_project()

        self.line("")

        if self.problems:
            self.error("  {} problem(s) to fix.".format(self.problems))
        elif self.cautions:
            self.warn("  {} thing(s) worth knowing about.".format(self.cautions))
        else:
            self.success("  Everything checks out.")

        self.line("")

        return 1 if self.problems else 0

    # -- python -----------------------------------------------------------

    def _check_python(self):
        self._heading("Python")

        version = "{}.{}.{}".format(*sys.version_info[:3])

        self._assert(
            "version",
            version,
            sys.version_info >= (3, 8),
            "Bazimya needs Python 3.8 or newer.",
        )

        self._note("binary", sys.executable)
        self._note("platform", sys.platform)

        for module in ("sqlite3", "ssl", "zlib"):
            try:
                __import__(module)
                self._note(module, "available")
            except ImportError:
                self.cautions += 1
                self.warn("    " + self._pad(module) + "missing")

                if module == "sqlite3":
                    self.line("    " + " " * self.LABEL_WIDTH + "The default database driver needs it.")

        for module, label in (("pymysql", "MySQL"), ("psycopg2", "PostgreSQL")):
            try:
                __import__(module)
                self._note(module, "installed ({})".format(label))
            except ImportError:
                pass

    # -- project ----------------------------------------------------------

    def _check_project(self):
        # Boot first: middleware groups, routes and extensions only exist once
        # app/Http/Kernel.py has been read, and several checks look at them.
        try:
            self.app.boot()
        except Exception as error:  # noqa: BLE001 — report it and keep going;
            # the rest of the checks are often what explains the failure.
            self.problems += 1
            self._heading("Boot")
            self.error("    the application failed to boot:")
            self.line("    " + " " * self.LABEL_WIDTH + str(error).split("\n")[0])

        self._check_writable()
        self._check_config()
        self._check_database()
        self._check_security()
        self._check_extensions()
        self._check_deployment()

    def _check_writable(self):
        self._heading("Writable directories")

        for relative in (
            "storage",
            "storage/framework/views",
            "storage/framework/sessions",
            "storage/framework/cache",
            "storage/logs",
            "database",
        ):
            path = self.app.path(relative)

            if not os.path.isdir(path):
                self._note(relative, "missing")
                continue

            self._assert(
                relative,
                "writable" if os.access(path, os.W_OK) else "NOT writable",
                os.access(path, os.W_OK),
                "chmod 775 {} — the app cannot run without it.".format(relative),
            )

    def _check_config(self):
        self._heading("Configuration")

        config = self.app.make("config")
        environment = str(config.get("app.env", "production"))
        debug = bool(config.get("app.debug", False))

        self._note("env", environment)

        if environment == "production" and debug:
            self.problems += 1
            self.error("    " + self._pad("debug") + "ON in production")
            self.line("    " + " " * self.LABEL_WIDTH + "Set APP_DEBUG=false. Stack traces leak credentials.")
        else:
            self._note("debug", "on" if debug else "off")

        if not config.get("app.key"):
            self.cautions += 1
            self.warn("    " + self._pad("key") + "not set")
            self.line("    " + " " * self.LABEL_WIDTH + "Set APP_KEY in .env.")

    def _check_database(self):
        self._heading("Database")

        config = self.app.make("config")
        default = config.get("database.default", "sqlite")

        self._note("driver", str(default))

        try:
            connection = self.app.make("db")
            connection.select("SELECT 1")
            self.success("    " + self._pad("connection") + "reachable")
        except Exception as error:  # noqa: BLE001 — report, do not raise
            self.problems += 1
            self.error("    " + self._pad("connection") + "unreachable")
            self.line("    " + " " * self.LABEL_WIDTH + str(error).split("\n")[0])

            return

        # A SQLite file inside public/ is downloadable over HTTP.
        database = str(config.get("database.connections.sqlite.database", ""))

        if default == "sqlite" and database and "public" in database.split(os.sep):
            self.problems += 1
            self.error("    " + self._pad("location") + "the SQLite file is inside public/")
            self.line("    " + " " * self.LABEL_WIDTH + "Move it to database/ — it is downloadable where it is.")

    def _check_security(self):
        self._heading("Security")

        from ...hashing import SCRYPT_AVAILABLE

        hasher = self.app.make("hash")
        configured = str(self.app.make("config").get("hashing.driver", "scrypt"))
        resolved = hasher.driver()

        self._note("password hash", resolved)

        if configured == "scrypt" and not SCRYPT_AVAILABLE:
            self.cautions += 1
            self.warn("    " + self._pad("") + "scrypt is not in this OpenSSL build;")
            self.line("    " + " " * self.LABEL_WIDTH + "using pbkdf2 instead, which is still sound.")

        router = self.app.make("router")
        groups = router.middleware_groups()
        web = [getattr(m, "__name__", str(m)) for m in groups.get("web", [])]

        has_csrf = any("VerifyCsrfToken" in name for name in web)
        has_session = any("StartSession" in name for name in web)

        self._assert(
            "CSRF",
            "on" if has_csrf else "OFF",
            has_csrf,
            "Add VerifyCsrfToken to the web group in app/Http/Kernel.py.",
            fatal=False,
        )
        self._assert(
            "sessions",
            "on" if has_session else "off",
            has_session,
            "Add StartSession to the web group if this app has logins.",
            fatal=False,
        )

        secure = bool(self.app.make("config").get("session.secure", False))

        if self.app.is_production() and not secure:
            self.cautions += 1
            self.warn("    " + self._pad("cookie secure") + "off in production")
            self.line("    " + " " * self.LABEL_WIDTH + "Set SESSION_SECURE_COOKIE=true once the site is on HTTPS.")
        else:
            self._note("cookie secure", "on" if secure else "off")

    def _check_extensions(self):
        if not os.path.isdir(self.app.extensions_path()):
            return

        self._heading("Extensions")

        try:
            manager = self.app.make("extensions")
        except Exception as error:  # noqa: BLE001
            self.problems += 1
            self.error("    could not load: " + str(error))

            return

        extensions = manager.all()

        if not extensions:
            self._note("found", "none")

        for extension in extensions:
            self._note(
                extension.name,
                "{} · {} command(s)".format(extension.version, len(extension.commands)),
            )

        for failure in manager.failures():
            self.problems += 1
            self.error("    {} — {}".format(failure["name"], failure["error"].split("\n")[0]))

    def _check_deployment(self):
        self._heading("Deployment")

        compiled = self.app.storage_path("framework", "views")
        count = len([f for f in os.listdir(compiled) if f.endswith(".py")]) if os.path.isdir(compiled) else 0

        self._note("compiled views", str(count))

        if count == 0:
            pad = "    " + " " * self.LABEL_WIDTH
            self.line(pad + "Run `bazimya view:cache` before deploying to a")
            self.line(pad + "host where storage/ is read-only.")

        for entry, label in (
            ("passenger_wsgi.py", "Passenger (cPanel)"),
            ("wsgi.py", "gunicorn / uWSGI"),
            ("public/index.py", "CGI fallback"),
        ):
            if os.path.isfile(self.app.path(entry)):
                self._note(entry, label)

    # -- output helpers ---------------------------------------------------

    def _heading(self, title):
        self.line("")
        self.comment("  " + title)

    LABEL_WIDTH = 22

    @classmethod
    def _pad(cls, label):
        # A label wider than the column still needs a separating space, or it
        # runs straight into its value.
        return label.ljust(cls.LABEL_WIDTH) if len(label) < cls.LABEL_WIDTH else label + "  "

    def _note(self, label, value):
        self.line("    " + self._pad(label) + str(value))

    def _assert(self, label, value, passed, advice, fatal=True):
        line = "    " + self._pad(label) + str(value)

        if passed:
            self.line(line)

            return

        if fatal:
            self.problems += 1
            self.error(line)
        else:
            self.cautions += 1
            self.warn(line)

        self.line("    " + " " * self.LABEL_WIDTH + advice)
