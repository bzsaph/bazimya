"""Discovering extensions and wiring them into the application."""

import importlib
import os
import sys
import traceback

from .extension import Extension, registry, reset_registry


class ExtensionManager:
    def __init__(self, application, paths=None, enabled=True, only=None, disabled=None):
        self.application = application
        self.paths = [p for p in (paths or []) if p]
        self.enabled = enabled
        self.only = list(only) if only else None
        self.disabled = set(disabled or [])

        self._extensions = None
        self._failures = []
        self._registered = False

    # -- discovery --------------------------------------------------------

    def names(self):
        """Every extension directory or module found, sorted."""
        found = []

        for path in self.paths:
            if not os.path.isdir(path):
                continue

            for entry in sorted(os.listdir(path)):
                if entry.startswith((".", "_")):
                    continue

                full = os.path.join(path, entry)

                if os.path.isdir(full) and os.path.isfile(os.path.join(full, "__init__.py")):
                    found.append((entry, path))
                elif entry.endswith(".py"):
                    found.append((entry[:-3], path))

        return found

    def all(self):
        if self._extensions is None:
            self._extensions = self._load()

        return self._extensions

    def failures(self):
        self.all()

        return list(self._failures)

    def find(self, name):
        for extension in self.all():
            if extension.name.lower() == str(name).lower():
                return extension

        return None

    def _load(self):
        if not self.enabled:
            return []

        reset_registry()
        loaded = []
        self._failures = []

        for name, path in self.names():
            if name in self.disabled or (self.only is not None and name not in self.only):
                continue

            # Importing from the extensions directory as a top-level package
            # is what makes relative imports inside an extension work.
            if path not in sys.path:
                sys.path.insert(0, path)

            before = len(registry())

            try:
                module = importlib.import_module(name)
            except Exception as error:  # noqa: BLE001 — one broken extension
                # must not take the site down.
                self._failures.append(
                    {
                        "name": name,
                        "error": "{}: {}".format(type(error).__name__, error),
                        "trace": traceback.format_exc(),
                    }
                )
                continue

            new = registry()[before:]

            if not new:
                self._failures.append(
                    {
                        "name": name,
                        "error": (
                            "No Extension was created. Add:\n\n"
                            "    from bazimya import Extension\n\n"
                            "    extension = Extension('{}')".format(name)
                        ),
                        "trace": "",
                    }
                )
                continue

            for extension in new:
                # Only a package can own views and migrations; a single module
                # sits directly in extensions/, where those would belong to
                # nobody in particular.
                if hasattr(module, "__path__"):
                    extension.path = os.path.dirname(os.path.abspath(module.__file__))

                loaded.append(extension)

        return loaded

    # -- registration -----------------------------------------------------

    def register(self, router, view=None):
        if self._registered:
            return self

        self._registered = True

        for extension in self.all():
            self._register_views(extension, view)
            self._register_middleware(extension, router)
            self._register_routes(extension, router)

        # Boot hooks run after everything is registered, so one extension can
        # rely on another's routes or middleware being present.
        for extension in self.all():
            for callback in extension.boot_callbacks:
                callback()

        return self

    def _register_views(self, extension, view):
        if view is None:
            return

        views_path = extension.views_path()

        if views_path:
            view.add_namespace(extension.view_namespace(), views_path)

    def _register_middleware(self, extension, router):
        for alias, handler in extension.middleware_aliases.items():
            router.alias_middleware(alias, _wrap_middleware(handler))

    def _register_routes(self, extension, router):
        if not extension.route_callbacks:
            return

        attributes = {
            "prefix": extension.prefix,
            "middleware": extension.middleware_stack,
        }

        for callback in extension.route_callbacks:
            router.group(attributes, callback)

    # -- introspection ----------------------------------------------------

    def commands(self):
        commands = []

        for extension in self.all():
            for command in extension.commands:
                commands.append(
                    {
                        "name": command.name,
                        "description": command.description,
                        "usage": command.usage,
                        "extension": extension.name,
                        "handler": command.handler,
                    }
                )

        return commands

    def find_command(self, name):
        for command in self.commands():
            if command["name"] == name:
                return command

        return None

    def migration_paths(self):
        paths = []

        for extension in self.all():
            path = extension.migrations_path()

            if path:
                paths.append(path)

        return paths


def _wrap_middleware(handler):
    """Adapt an extension middleware function to the router's contract.

    Extension middleware is written as `def check(request)` returning either
    None (carry on) or a response (stop). Full `next` semantics are available
    by writing a Middleware class instead; this shorthand covers the common
    before-the-handler case.
    """
    import inspect

    if inspect.isclass(handler):
        return handler

    try:
        parameters = list(inspect.signature(handler).parameters)
    except (TypeError, ValueError):
        parameters = ["request"]

    # A two-argument handler already speaks (request, next).
    if len(parameters) >= 2:
        return handler

    def middleware(request, next_handler):
        result = handler(request)

        return next_handler(request) if result is None else result

    return middleware
