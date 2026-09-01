"""Extensions — self-contained packages that plug into an application.

An extension is a Python package under extensions/ that declares its routes,
commands, middleware, views and migrations. It is Laravel's service provider,
with the pieces a package usually ships bundled in:

    # extensions/Blog/__init__.py
    from bazimya import Extension, Route, Response

    extension = Extension(
        'Blog',
        version='1.0.0',
        description='Posts and comments.',
        prefix='blog',
    )


    class PostController(extension.Controller):
        def index(self, request):
            return self.view('blog::index', posts=Post.all())


    @extension.routes
    def routes():
        Route.get('/', [PostController, 'index']).name('blog.index')
        Route.resource('posts', PostController)


    @extension.command('blog:publish', 'Publish scheduled posts')
    def publish(args, options):
        return 'Published.'

Routes go inside `@extension.routes` rather than at module top level so the
manager can register them under the extension's prefix and middleware — it
needs to have read the metadata before the routes are declared.
"""

import os

from ..http.controller import Controller
from ..http.request import Request
from ..http.response import Response

#: Extensions register themselves here as their modules are imported.
_registry = []


class ExtensionCommand:
    def __init__(self, name, description, handler, usage=None):
        self.name = name
        self.description = description
        self.handler = handler
        self.usage = usage or "bazimya {}".format(name)


class Extension:
    #: So a module needs one import to get everything.
    Controller = Controller
    Request = Request
    Response = Response

    def __init__(
        self,
        name,
        version="0.1.0",
        description="",
        prefix=None,
        middleware=None,
        views="views",
        migrations="migrations",
        requires=None,
    ):
        self.name = name
        self.version = version
        self.description = description
        self.prefix = (prefix or "").strip("/")
        self.middleware_stack = list(middleware or [])
        self.views_directory = views
        self.migrations_directory = migrations
        self.requires = list(requires or [])

        self.route_callbacks = []
        self.commands = []
        self.middleware_aliases = {}
        self.boot_callbacks = []
        self.config_defaults = {}

        #: Filled in by the manager once it knows where the module came from.
        self.path = None

        _registry.append(self)

    # -- declarations -----------------------------------------------------

    def routes(self, callback):
        """Register this extension's routes.

            @extension.routes
            def routes():
                Route.get('/posts', [PostController, 'index'])
        """
        self.route_callbacks.append(callback)

        return callback

    def command(self, name, description="", usage=None):
        """Add a CLI command, runnable as `bazimya <name>`.

        The handler is called with (args, options): positional arguments as a
        list, --options as a dict. Return a string to print it, or an int to
        use as the exit code.
        """

        def decorator(handler):
            self.commands.append(ExtensionCommand(name, description, handler, usage))

            return handler

        return decorator

    def middleware_alias(self, alias):
        """Register middleware under a short name, usable from any route."""

        def decorator(handler):
            self.middleware_aliases[alias] = handler

            return handler

        return decorator

    def booting(self, callback):
        """Run once, after the extension has been registered."""
        self.boot_callbacks.append(callback)

        return callback

    def defaults(self, values):
        """Config defaults, merged under `extensions.<name>` if not set."""
        self.config_defaults.update(values or {})

        return self

    # -- paths ------------------------------------------------------------

    def views_path(self):
        if not self.path or not self.views_directory:
            return None

        path = os.path.join(self.path, self.views_directory)

        return path if os.path.isdir(path) else None

    def migrations_path(self):
        if not self.path or not self.migrations_directory:
            return None

        path = os.path.join(self.path, self.migrations_directory)

        return path if os.path.isdir(path) else None

    def view_namespace(self):
        return self.name.lower()

    def config(self, key, default=None):
        from ..facades import Config

        full = "extensions.{}.{}".format(self.name.lower(), key)
        value = Config.get(full, None)

        return self.config_defaults.get(key, default) if value is None else value

    def to_dict(self):
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "prefix": self.prefix,
            "path": self.path,
            "views": self.views_path(),
            "migrations": self.migrations_path(),
            "commands": [
                {"name": c.name, "description": c.description, "usage": c.usage}
                for c in self.commands
            ],
            "middleware": sorted(self.middleware_aliases),
            "requires": self.requires,
        }

    def __repr__(self):
        return "<Extension {} {}>".format(self.name, self.version)


def registry():
    return list(_registry)


def reset_registry():
    _registry.clear()
