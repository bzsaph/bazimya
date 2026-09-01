"""The application: paths, container bindings and the request lifecycle.

The boot order is fixed, because the ordering is what makes the
extension points useful:

    1. .env, then config/
    2. core container bindings
    3. service providers register()
    4. app/Http/Kernel.py — global middleware, groups, aliases
    5. routes/web.py, then routes/api.py under /api
    6. Python extensions
    7. service providers boot()

Routes come before extensions so an application route always wins over an
extension route on the same URI.
"""

import importlib
import os
import sys
import traceback

from ..database.connection import Connection
from ..http.exceptions import HttpException
from ..http.request import Request
from ..http.response import Response
from ..http.router import Router
from ..support.config import Repository
from ..support.env import Env
from ..view.view import View
from .container import Container

VERSION = "0.2.1"


class Application(Container):
    _instance = None

    def __init__(self, base_path=None):
        super().__init__()

        self.base_path = os.path.abspath(base_path or os.getcwd())
        self.booted = False
        self._providers = []
        self._migration_paths = []

        Application._instance = self

        # The project root has to be importable before anything tries to load
        # app.Http.Controllers or routes/web.py.
        if self.base_path not in sys.path:
            sys.path.insert(0, self.base_path)

        Env.load(self.path(".env"))

        self._register_core_bindings()

    # -- singleton access -------------------------------------------------

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            raise RuntimeError(
                "No Bazimya application has been created. Run this from inside "
                "a project, or create one with: bazimya new my-app"
            )

        return cls._instance

    @classmethod
    def set_instance(cls, application):
        cls._instance = application

    def version(self):
        return VERSION

    # -- paths ------------------------------------------------------------

    def path(self, *parts):
        return os.path.join(self.base_path, *parts) if parts else self.base_path

    def app_path(self, *parts):
        return self.path("app", *parts)

    def config_path(self, *parts):
        return self.path("config", *parts)

    def database_path(self, *parts):
        return self.path("database", *parts)

    def migrations_path(self, *parts):
        return self.path("database", "migrations", *parts)

    def public_path(self, *parts):
        return self.path("public", *parts)

    def resource_path(self, *parts):
        return self.path("resources", *parts)

    def views_path(self, *parts):
        return self.path("resources", "views", *parts)

    def routes_path(self, *parts):
        return self.path("routes", *parts)

    def storage_path(self, *parts):
        return self.path("storage", *parts)

    def bootstrap_path(self, *parts):
        return self.path("bootstrap", *parts)

    def extensions_path(self, *parts):
        return self.path("extensions", *parts)

    def add_migration_path(self, path):
        """Let a provider or extension contribute migrations to `migrate`."""
        if path and path not in self._migration_paths:
            self._migration_paths.append(path)

        return self

    def migration_paths(self):
        """Every directory `bazimya migrate` should look in.

        The application's own comes first so its migrations sort ahead of an
        extension's when timestamps collide.
        """
        paths = [self.migrations_path()]
        paths.extend(self._migration_paths)

        try:
            paths.extend(self.make("extensions").migration_paths())
        except Exception:  # noqa: BLE001 — migrating must work even if an
            # extension is broken; `extension:list` reports that separately.
            pass

        seen = []

        for path in paths:
            if path and path not in seen:
                seen.append(path)

        return seen

    def framework_path(self, *parts):
        """Where the framework itself lives, which is not inside the app."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        return os.path.join(root, *parts) if parts else root

    # -- environment ------------------------------------------------------

    def environment(self):
        return str(self.make("config").get("app.env", "production"))

    def is_local(self):
        return self.environment() == "local"

    def is_production(self):
        return self.environment() == "production"

    def has_debug_mode(self):
        return bool(self.make("config").get("app.debug", False))

    # -- container --------------------------------------------------------

    def _register_core_bindings(self):
        self.instance("app", self)

        self.singleton("config", lambda c: Repository(self.config_path()))

        self.singleton("router", lambda c: Router(c))

        self.singleton(
            "view",
            lambda c: View(
                self.views_path(),
                self.storage_path("framework", "views"),
                debug=bool(c.make("config").get("app.debug", False)),
                root=self.base_path,
            ),
        )

        self.singleton("db", lambda c: self._make_connection(c))

        self.singleton("extensions", lambda c: self._make_extension_manager(c))

        self.singleton("hash", lambda c: self._make_hasher(c))
        self.singleton("session", lambda c: self._make_session(c))
        self.singleton("auth", lambda c: self._make_auth(c))
        self.singleton("cache", lambda c: self._make_cache(c))
        self.singleton("storage", lambda c: self._make_filesystem(c))
        self.singleton("mail", lambda c: self._make_mailer(c))
        self.singleton("events", lambda c: self._make_events(c))
        self.singleton("notify", lambda c: self._make_notifier(c))

    def _make_hasher(self, container):
        from ..hashing import Hasher

        return Hasher(container.make("config").get("hashing", {}) or {})

    def _make_session(self, container):
        from ..session.store import ArraySessionHandler, FileSessionHandler, SessionStore

        config = container.make("config")
        driver = str(config.get("session.driver", "file"))
        lifetime = int(config.get("session.lifetime", 120) or 120)

        if driver == "array":
            handler = ArraySessionHandler()
        else:
            handler = FileSessionHandler(
                self.storage_path("framework", "sessions"), lifetime
            )

        return SessionStore(
            handler, str(config.get("session.cookie", "bazimya_session")), lifetime
        )

    def _make_auth(self, container):
        from ..auth.guard import SessionGuard

        config = container.make("config")
        guard = str(config.get("auth.defaults.guard", "web"))
        provider = config.get("auth.guards.{}.provider".format(guard), "users")

        return SessionGuard(
            self, config.get("auth.providers.{}".format(provider), {}) or {}
        )

    def _make_cache(self, container):
        from ..cache.repository import ArrayStore, CacheRepository, FileStore, NullStore

        config = container.make("config")
        driver = str(config.get("cache.default", "file"))

        if driver == "array":
            store = ArrayStore()
        elif driver == "null":
            store = NullStore()
        else:
            store = FileStore(
                config.get("cache.stores.file.path")
                or self.storage_path("framework", "cache")
            )

        return CacheRepository(store)

    def _make_filesystem(self, container):
        from ..filesystem.storage import FilesystemManager

        return FilesystemManager(
            container.make("config").get("filesystems", {}) or {}, self.base_path
        )

    def _make_mailer(self, container):
        from ..mail.mailer import Mailer

        return Mailer(container.make("config").get("mail", {}) or {}, self)

    def _make_events(self, container):
        from ..events.dispatcher import Dispatcher

        return Dispatcher()

    def _make_notifier(self, container):
        from ..notifications.notification import NotificationSender

        return NotificationSender(self)

    def _make_connection(self, container):
        config = container.make("config")
        default = config.get("database.default", "sqlite")
        settings = config.get("database.connections.{}".format(default), {}) or {}

        # The config file names the connection; the driver is part of it, but
        # defaulting to the connection name covers a hand-edited config.
        settings = dict(settings)
        settings.setdefault("driver", default)

        return Connection(settings, self.base_path)

    def _make_extension_manager(self, container):
        from ..extensions.manager import ExtensionManager

        config = container.make("config")

        return ExtensionManager(
            application=self,
            paths=[self.extensions_path()],
            enabled=bool(config.get("extensions.enabled", True)),
        )

    # -- booting ----------------------------------------------------------

    def boot(self):
        if self.booted:
            return self

        self.booted = True

        self._register_providers()
        self._load_http_kernel()
        self._load_routes()
        self._load_extensions()
        self._boot_providers()

        return self

    def _register_providers(self):
        """Load the classes named in config/app.py's `providers` list."""
        for reference in self.make("config").get("app.providers", []) or []:
            provider = self._resolve_class(reference)

            if provider is None:
                continue

            instance = provider(self)
            self._providers.append(instance)

            if hasattr(instance, "register"):
                instance.register()

    def _boot_providers(self):
        for provider in self._providers:
            if hasattr(provider, "boot"):
                provider.boot()

    def _load_http_kernel(self):
        """app/Http/Kernel.py declares global middleware, groups and aliases."""
        kernel = self._resolve_class("app.Http.Kernel.Kernel")

        if kernel is None:
            return

        router = self.make("router")
        instance = kernel()

        for middleware in getattr(instance, "middleware", []) or []:
            router.push_middleware(middleware)

        for name, group in (getattr(instance, "middleware_groups", {}) or {}).items():
            router.middleware_group(name, group)

        for alias, middleware in (getattr(instance, "middleware_aliases", {}) or {}).items():
            router.alias_middleware(alias, middleware)

    #: Route files with a meaning of their own; everything else in routes/ is
    #: loaded into the web group.
    RESERVED_ROUTE_FILES = ("web.py", "api.py", "console.py", "channels.py", "__init__.py")

    def _load_routes(self):
        router = self.make("router")

        # web.py first, then any other route file (auth.py, admin.py …) in the
        # same group. Dropping a file into routes/ is enough — there is no
        # import line to remember, and nothing to keep in sync.
        web_files = []
        web = self.routes_path("web.py")

        if os.path.isfile(web):
            web_files.append(web)

        if os.path.isdir(self.routes_path()):
            for entry in sorted(os.listdir(self.routes_path())):
                if entry.endswith(".py") and entry not in self.RESERVED_ROUTE_FILES:
                    web_files.append(self.routes_path(entry))

        if web_files:
            router.group(
                {"middleware": ["web"] if router.has_middleware_group("web") else []},
                lambda: [
                    self._load_route_file(path, "routes." + os.path.basename(path)[:-3])
                    for path in web_files
                ],
            )

        # API routes get the /api prefix and the api middleware group, which
        # is what RouteServiceProvider does.
        api = self.routes_path("api.py")

        if os.path.isfile(api):
            router.group(
                {
                    "prefix": self.make("config").get("app.api_prefix", "api"),
                    "middleware": ["api"] if router.has_middleware_group("api") else [],
                },
                lambda: self._load_route_file(api, "routes.api"),
            )

    def _load_route_file(self, path, module_name):
        """Execute a route file so its Route.get(...) calls register.

        The module is dropped from sys.modules first: routes register by side
        effect, and a cached module is not re-executed — so a second
        Application in the same process (every test after the first) would
        come up with no routes at all.
        """
        sys.modules.pop(module_name, None)

        spec = importlib.util.spec_from_file_location(module_name, path)

        if spec is None or spec.loader is None:
            return

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        finally:
            # Leaving it registered would make the next load a no-op again.
            sys.modules.pop(module_name, None)

    def load_console_routes(self):
        """Load routes/console.py.

        Only the CLI needs these, so they are not loaded during a web request —
        importing them there would be pure cost on every page.
        """
        path = self.routes_path("console.py")

        if os.path.isfile(path):
            self._load_route_file(path, "routes.console")

        return self

    def console_commands(self):
        """Command classes from app/Console/Kernel.py, plus routes/console.py."""
        self.load_console_routes()

        kernel = self._resolve_class("app.Console.Kernel.Kernel")
        classes = list(getattr(kernel(), "commands", []) or []) if kernel else []

        from ..console.registry import Console

        return classes, Console.all()

    def _load_extensions(self):
        try:
            self.make("extensions").register(self.make("router"), self.make("view"))
        except Exception:  # noqa: BLE001
            # A broken extension should not take the whole site down; the
            # manager records the failure and `extension:list` reports it.
            if self.has_debug_mode():
                raise

    def _resolve_class(self, reference):
        """Import 'app.Http.Kernel.Kernel' and return the class."""
        if not isinstance(reference, str):
            return reference

        module_name, _, class_name = reference.rpartition(".")

        if not module_name:
            return None

        try:
            module = importlib.import_module(module_name)
        except ImportError:
            return None

        return getattr(module, class_name, None)

    # -- handling requests ------------------------------------------------

    def handle(self, request):
        self.boot()

        router = self.make("router")

        def dispatch(req):
            try:
                return Response.make(router.dispatch(req))
            except Exception as error:  # noqa: BLE001 — this is the last line
                return self.render_exception(req, error)

        pipeline = dispatch

        # Global middleware wraps the error rendering too, so a 404 still gets
        # the response headers every other page gets.
        for middleware in reversed(router.global_middleware()):
            pipeline = router.wrap_middleware(middleware, pipeline)

        try:
            return Response.make(pipeline(request))
        except Exception as error:  # noqa: BLE001 — a middleware itself failed
            return self.render_exception(request, error)

    def render_exception(self, request, error):
        handler = self._resolve_class("app.Exceptions.Handler.Handler")

        if handler is not None:
            try:
                rendered = handler(self).render(request, error)

                if rendered is not None:
                    return Response.make(rendered)
            except Exception:  # noqa: BLE001 — fall through to the default
                pass

        return self.default_exception_response(request, error)

    def default_exception_response(self, request, error):
        status = error.status if isinstance(error, HttpException) else 500
        debug = self.has_debug_mode()

        self.log_exception(error, status)

        if request.wants_json():
            payload = {"message": str(error) if debug or status < 500 else "Server Error"}

            if debug and status >= 500:
                payload["exception"] = type(error).__name__
                payload["trace"] = traceback.format_exc().splitlines()

            return Response.json(payload, status)

        view = self.make("view")
        template = "errors.{}".format(status)

        if view.exists(template):
            try:
                return Response.html(
                    view.render(template, {"exception": error, "status": status}), status
                )
            except Exception:  # noqa: BLE001 — never fail inside the error page
                pass

        if debug:
            return Response.html(_debug_page(error, status, request), status)

        from ..http.response import STATUS_TEXT

        return Response.html(
            "<h1>{} — {}</h1>".format(status, STATUS_TEXT.get(status, "Error")), status
        )

    def log_exception(self, error, status):
        """Append 5xx errors to storage/logs. A 404 is not worth a log line."""
        if status < 500:
            return

        try:
            directory = self.storage_path("logs")
            os.makedirs(directory, exist_ok=True)

            from datetime import datetime

            with open(os.path.join(directory, "bazimya.log"), "a", encoding="utf-8") as handle:
                handle.write(
                    "[{}] {}: {}\n{}\n".format(
                        datetime.now().isoformat(timespec="seconds"),
                        type(error).__name__,
                        error,
                        traceback.format_exc(),
                    )
                )
        except OSError:
            # An unwritable storage/ is worth knowing about, but not worth
            # replacing the user's error with a different one.
            pass

    # -- WSGI -------------------------------------------------------------

    def __call__(self, environ, start_response):
        """The application is itself a WSGI app.

        Passenger, gunicorn and the dev server all enter here.
        """
        request = Request.from_environ(environ)
        response = self.handle(request)

        start_response(response.status_line(), response.header_list())

        body = response.body_bytes()

        # HEAD must carry the headers of a GET but none of the body.
        if request.method() == "HEAD" or response.status in (204, 304):
            return [b""]

        return [body]


def _debug_page(error, status, request):
    import html as html_module

    trace = html_module.escape(traceback.format_exc())

    return """<!doctype html>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{status} {name}</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 14px/1.6 ui-monospace, SFMono-Regular, Menlo, monospace; margin: 0; padding: 2rem; }}
 h1 {{ font-size: 1.25rem; margin: 0 0 .25rem; }}
 .m {{ color: #b00020; font-size: 1.05rem; margin: 0 0 1.5rem; }}
 pre {{ background: rgba(127,127,127,.12); padding: 1rem; overflow-x: auto; border-radius: 6px; }}
 .r {{ opacity: .7; margin-bottom: 1.5rem; }}
</style>
<h1>{status} · {name}</h1>
<p class="m">{message}</p>
<p class="r">{method} {path}</p>
<pre>{trace}</pre>
<p class="r">Set APP_DEBUG=false to hide this page.</p>
""".format(
        status=status,
        name=html_module.escape(type(error).__name__),
        message=html_module.escape(str(error)) or "&nbsp;",
        method=html_module.escape(request.method()),
        path=html_module.escape(request.path()),
        trace=trace,
    )
