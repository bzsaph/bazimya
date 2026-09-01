"""Facades — static-looking access to what is in the container.

    from bazimya import Route, DB, View, Config

    Route.get('/', [HomeController, 'index'])
    DB.table('users').where('active', 1).get()

Each facade forwards to a container binding, resolved on first use. That
indirection is what lets routes/web.py call `Route.get(...)` at import time,
before the router it will end up on has necessarily been built.
"""


class Facade:
    """Forwards attribute access to a container binding."""

    #: The container key this facade stands in for.
    binding = None

    @classmethod
    def resolve(cls):
        from .foundation.application import Application

        return Application.get_instance().make(cls.binding)

    def __getattr__(self, name):
        return getattr(type(self).resolve(), name)

    def __call__(self, *args, **kwargs):
        return type(self).resolve()(*args, **kwargs)

    def __repr__(self):
        return "<Facade {}>".format(type(self).binding)


class _RouteFacade(Facade):
    binding = "router"


class _DBFacade(Facade):
    binding = "db"

    def connection(self):
        return type(self).resolve()

    def table(self, name):
        return type(self).resolve().table(name)

    def select(self, sql, bindings=None):
        return type(self).resolve().select(sql, bindings)

    def statement(self, sql, bindings=None):
        return type(self).resolve().statement(sql, bindings)

    def transaction(self, callback):
        return type(self).resolve().transaction(callback)


class _ViewFacade(Facade):
    binding = "view"

    def render(self, template, data=None, **kwargs):
        return type(self).resolve().render(template, data, **kwargs)

    def exists(self, template):
        return type(self).resolve().exists(template)

    def share(self, key, value=None):
        return type(self).resolve().share(key, value)


class _ConfigFacade(Facade):
    binding = "config"

    def get(self, key, default=None):
        return type(self).resolve().get(key, default)

    def set(self, key, value):
        return type(self).resolve().set(key, value)

    def has(self, key):
        return type(self).resolve().has(key)

    def all(self):
        return type(self).resolve().all()


class _AppFacade(Facade):
    binding = "app"


class _ExtensionFacade(Facade):
    binding = "extensions"


class _HashFacade(Facade):
    binding = "hash"

    def make(self, value):
        return type(self).resolve().make(value)

    def check(self, value, hashed):
        return type(self).resolve().check(value, hashed)

    def needs_rehash(self, hashed):
        return type(self).resolve().needs_rehash(hashed)


class _SessionFacade(Facade):
    binding = "session"


class _AuthFacade(Facade):
    binding = "auth"

    def user(self):
        return type(self).resolve().user()

    def check(self):
        return type(self).resolve().check()

    def guest(self):
        return type(self).resolve().guest()

    def id(self):
        return type(self).resolve().id()

    def attempt(self, credentials, remember=False):
        return type(self).resolve().attempt(credentials, remember)

    def login(self, user, remember=False):
        return type(self).resolve().login(user, remember)

    def logout(self):
        return type(self).resolve().logout()

    def set_session(self, session):
        return type(self).resolve().set_session(session)


class _CacheFacade(Facade):
    binding = "cache"


class _StorageFacade(Facade):
    binding = "storage"

    def disk(self, name=None):
        return type(self).resolve().disk(name)


class _MailFacade(Facade):
    binding = "mail"

    def to(self, *addresses):
        return type(self).resolve().to(*addresses)


class _EventFacade(Facade):
    binding = "events"

    def listen(self, event, listener=None):
        return type(self).resolve().listen(event, listener)

    def dispatch(self, event, payload=None):
        return type(self).resolve().dispatch(event, payload)


class _NotifyFacade(Facade):
    binding = "notify"

    def send(self, notifiables, notification):
        return type(self).resolve().send(notifiables, notification)


Route = _RouteFacade()
Hash = _HashFacade()
Session = _SessionFacade()
Auth = _AuthFacade()
Cache = _CacheFacade()
Storage = _StorageFacade()
Mail = _MailFacade()
Event = _EventFacade()
Notify = _NotifyFacade()
DB = _DBFacade()
View = _ViewFacade()
Config = _ConfigFacade()
App = _AppFacade()
Extensions = _ExtensionFacade()


# -- global helper functions ------------------------------------------------


def app(key=None):
    from .foundation.application import Application

    application = Application.get_instance()

    return application if key is None else application.make(key)


def config(key, default=None):
    return Config.get(key, default)


def view(template, data=None, **kwargs):
    """Render a template into a Response."""
    from .http.response import Response

    return Response.html(View.render(template, data, **kwargs))


def route(name, **parameters):
    return Route.url(name, **parameters)


def redirect(location, status=302):
    from .http.response import Response

    return Response.redirect(location, status)


def auth():
    """The currently authenticated user, or None."""
    return Auth.user()


def csrf_token():
    from .foundation.application import Application

    session = Application.get_instance().make("session")

    return session.token()


def old(key=None, default=None):
    """Input flashed by the previous request, for re-rendering a form."""
    from .foundation.application import Application

    return Application.get_instance().make("session").old(key, default)


def back(request, fallback="/"):
    from .http.response import Response

    return Response.redirect(request.header("referer") or fallback)


def base_path(*parts):
    return app().path(*parts)


def storage_path(*parts):
    return app().storage_path(*parts)


def public_path(*parts):
    return app().public_path(*parts)


def resource_path(*parts):
    return app().resource_path(*parts)


def database_path(*parts):
    return app().database_path(*parts)
