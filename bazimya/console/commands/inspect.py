"""Commands that show you what the application currently is."""

import os

from ..command import Command


class RouteListCommand(Command):
    name = "route:list"

    description = "List the registered routes"

    usage = "bazimya route:list [--method=GET] [--path=posts] [--name=posts.]"

    def handle(self):
        application = self.application()
        application.boot()

        routes = application.make("router").routes()

        method_filter = self.option("method")
        path_filter = self.option("path")
        name_filter = self.option("name")

        rows = []

        for route in routes:
            methods = [m for m in route.methods if m != "HEAD"] or route.methods

            if method_filter and method_filter.upper() not in methods:
                continue

            if path_filter and path_filter not in route.uri:
                continue

            if name_filter and not str(route.route_name or "").startswith(name_filter):
                continue

            rows.append(
                [
                    "|".join(methods),
                    route.uri,
                    route.route_name or "—",
                    self._describe(route.action),
                    ", ".join(str(m) for m in route.gather_middleware()) or "—",
                ]
            )

        self.line("")

        if not rows:
            self.comment("  No routes matched." if routes else "  No routes registered.")
            self.line("")

            return 0

        self.table(["Method", "URI", "Name", "Action", "Middleware"], rows)
        self.line("")
        self.comment("  {} route{}.".format(len(rows), "" if len(rows) == 1 else "s"))
        self.line("")

        return 0

    @staticmethod
    def _describe(action):
        if isinstance(action, (list, tuple)) and len(action) == 2:
            target, method = action

            return "{}@{}".format(getattr(target, "__name__", target), method)

        name = getattr(action, "__qualname__", None) or getattr(action, "__name__", None)

        return name or "closure"


class ExtensionListCommand(Command):
    name = "extension:list"

    description = "List the installed extensions"

    usage = "bazimya extension:list [--routes] [--commands]"

    def handle(self):
        application = self.application()
        application.boot()

        manager = application.make("extensions")
        extensions = manager.all()
        failures = manager.failures()

        self.line("")

        if not extensions and not failures:
            self.comment("  No extensions installed.")
            self.line("")
            self.line("  Create one with:")
            self.line("")
            self.line("      bazimya make:extension Blog")
            self.line("")

            return 0

        if extensions:
            rows = [
                [
                    extension.name,
                    extension.version,
                    "/" + extension.prefix if extension.prefix else "/",
                    str(len(extension.commands)),
                    extension.description or "—",
                ]
                for extension in extensions
            ]

            self.table(["Extension", "Version", "Prefix", "Commands", "Description"], rows)

        if self.flag("commands"):
            self._render_commands(manager)

        if failures:
            self.line("")
            self.error("  {} extension(s) failed to load:".format(len(failures)))
            self.line("")

            for failure in failures:
                self.line("    " + failure["name"])
                self.line("      " + failure["error"].replace("\n", "\n      "))

        self.line("")

        return 1 if failures else 0

    def _render_commands(self, manager):
        rows = [
            [command["name"], command["extension"], command["description"]]
            for command in manager.commands()
        ]

        self.line("")

        if not rows:
            self.comment("  No extension commands.")

            return

        self.table(["Command", "Extension", "Description"], rows)


class CacheClearCommand(Command):
    name = "cache:clear"

    description = "Clear the compiled templates"

    usage = "bazimya cache:clear"

    def handle(self):
        cleared = self.application().make("view").clear_cache()

        self.line("")
        self.success("  Cleared {} compiled template{}.".format(cleared, "" if cleared == 1 else "s"))
        self.line("")

        return 0


class ViewCacheCommand(Command):
    name = "view:cache"

    description = "Compile every template ahead of time"

    usage = "bazimya view:cache"

    def handle(self):
        from ...view.view import EXTENSION

        application = self.application()
        view = application.make("view")

        directories = [application.views_path()]

        application.boot()

        for paths in view.namespaces().values():
            directories.extend(paths)

        compiled = 0
        failed = []

        self.line("")

        for directory in directories:
            if not os.path.isdir(directory):
                continue

            for root, _, files in os.walk(directory):
                for entry in files:
                    if not entry.endswith(EXTENSION):
                        continue

                    path = os.path.join(root, entry)

                    try:
                        source = view._compile(path, os.path.relpath(path, directory))
                        view._write_cache(view._cache_file(path), source)
                        compiled += 1
                    except Exception as error:  # noqa: BLE001 — report them all
                        failed.append((path, str(error)))

        if failed:
            self.error("  {} template(s) failed to compile:".format(len(failed)))
            self.line("")

            for path, message in failed:
                self.line("    " + self.relative(path))
                self.line("      " + message)

            self.line("")

        self.success("  Compiled {} template{}.".format(compiled, "" if compiled == 1 else "s"))
        self.line("")
        self.comment("  Do this before deploying — it removes the first-hit compile cost")
        self.comment("  and works on hosts where storage/ is read-only.")
        self.line("")

        return 1 if failed else 0


class TinkerCommand(Command):
    name = "tinker"

    description = "Open a Python REPL with the application booted"

    usage = "bazimya tinker"

    def handle(self):
        import code

        application = self.application()
        application.boot()

        import bazimya

        namespace = {
            "app": application,
            "bazimya": bazimya,
            "Route": bazimya.Route,
            "DB": bazimya.DB,
            "View": bazimya.View,
            "Config": bazimya.Config,
            "Model": bazimya.Model,
            "Schema": bazimya.Schema,
        }

        # Models are what you almost always want in a REPL, so load them.
        loaded = self._load_models(application, namespace)

        banner = "\n  Bazimya {} — tinker\n".format(application.version())
        banner += "  Available: app, Route, DB, View, Config, Schema"

        if loaded:
            banner += ", " + ", ".join(loaded)

        banner += "\n  Ctrl+D to exit.\n"

        try:
            import readline  # noqa: F401 — importing it enables line editing
        except ImportError:
            pass

        code.interact(banner=banner, local=namespace, exitmsg="")

        return 0

    @staticmethod
    def _load_models(application, namespace):
        import importlib

        directory = application.app_path("Models")

        if not os.path.isdir(directory):
            return []

        loaded = []

        for entry in sorted(os.listdir(directory)):
            if not entry.endswith(".py") or entry.startswith("_"):
                continue

            name = entry[:-3]

            try:
                module = importlib.import_module("app.Models.{}".format(name))
                model = getattr(module, name, None)

                if model is not None:
                    namespace[name] = model
                    loaded.append(name)
            except Exception:  # noqa: BLE001 — a broken model should not stop
                # the REPL from opening; that is often why you opened it.
                continue

        return loaded
