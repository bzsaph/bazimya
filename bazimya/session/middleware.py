"""Session and CSRF middleware."""

import random

from ..http.exceptions import PageExpired
from ..http.middleware import Middleware
from ..http.response import Response
from .store import SessionStore


class StartSession(Middleware):
    """Load the session before the handler, save it after.

    Put this in the `web` middleware group. API routes usually should not have
    it — a token-authenticated request has no session to resume, and issuing a
    cookie for one is just overhead.
    """

    def handle(self, request, next):
        from ..facades import app

        application = app()
        config = application.make("config")
        session = application.make("session")

        key = str(config.get("app.key", "") or "")
        cookie_name = str(config.get("session.cookie", "bazimya_session"))

        signed = request.cookie(cookie_name)
        session_id = SessionStore.unsign(signed, key) if signed else None

        session.start(session_id)

        # The request needs a way to reach the session; `request.session()`
        # reads this.
        request.set("session", session)

        response = Response.make(next(request))

        if not session.save():
            self._warn_once(application)

        response.cookie(
            cookie_name,
            SessionStore.sign(session.id, key),
            minutes=int(config.get("session.lifetime", 120)),
            path=str(config.get("session.path", "/")),
            domain=config.get("session.domain") or None,
            secure=bool(config.get("session.secure", False)),
            http_only=bool(config.get("session.http_only", True)),
            same_site=str(config.get("session.same_site", "Lax")),
        )

        # Sweeping every request would be wasteful; a small chance per request
        # keeps the directory from growing without a cron job.
        lottery = config.get("session.lottery", [2, 100]) or [2, 100]

        if random.randint(1, int(lottery[1])) <= int(lottery[0]):
            handler = getattr(session, "handler", None)

            if handler is not None and hasattr(handler, "gc"):
                handler.gc()

        return response


    #: Warn once per process, not once per request.
    _warned = False

    @classmethod
    def _warn_once(cls, application):
        if cls._warned:
            return

        cls._warned = True

        import sys

        sys.stderr.write(
            "\nBazimya: the session could not be saved to {}.\n"
            "Every request will get a new CSRF token, so form POSTs will fail\n"
            "with 419. Make the directory writable:\n\n"
            "    chmod -R 775 storage\n\n".format(
                application.storage_path("framework", "sessions")
            )
        )


class VerifyCsrfToken(Middleware):
    """Reject state-changing requests that do not carry the session token.

    Without this, any other site can make a logged-in visitor's browser submit
    a form to yours. `@csrf` in a template renders the matching field.

    Add URIs to `exclude` for endpoints that are authenticated some other way
    — a webhook signed by the sender, for instance.
    """

    #: URIs skipped entirely. Supports a trailing * wildcard.
    exclude = []

    READ_METHODS = ("GET", "HEAD", "OPTIONS")

    def handle(self, request, next):
        if request.method() in self.READ_METHODS or self._excluded(request):
            return next(request)

        session = request.get("session")

        if session is None:
            # No session means nothing to protect, and no token to check
            # against; refusing here would break API routes that opt out of
            # StartSession on purpose.
            return next(request)

        if self._matches(request, session):
            return next(request)

        raise PageExpired(
            "The CSRF token is missing or does not match. Add @csrf inside the "
            "form, or send the X-CSRF-TOKEN header."
        )

    def _matches(self, request, session):
        import hmac

        expected = session.token()

        if not expected:
            return False

        provided = (
            request.input("_token")
            or request.header("x-csrf-token")
            or request.header("x-xsrf-token")
        )

        if not provided:
            return False

        return hmac.compare_digest(str(expected), str(provided))

    def _excluded(self, request):
        path = request.path()

        for pattern in self.exclude:
            pattern = "/" + str(pattern).strip("/")

            if pattern.endswith("/*"):
                if path.startswith(pattern[:-1]):
                    return True
            elif path == pattern:
                return True

        return False


class ShareErrorsFromSession(Middleware):
    """Make `errors` and `old` available to every template.

    A failed validation redirects back, and the form needs both to re-render
    itself with the messages and the values the user typed.
    """

    def handle(self, request, next):
        from ..facades import app

        session = request.get("session")

        if session is not None:
            view = app().make("view")
            errors = session.errors()
            values = session.old()

            # `errors` is a dict so a template can write `field in errors` and
            # `errors[field]`; `old` is callable because Laravel's helper is —
            # `old('email', '')` is what a form field looks like.
            view.share("errors", errors)
            view.share("old", _OldInput(values))
            view.set_csrf_token(session.token())

        return next(request)


class _OldInput:
    """Flashed input, usable as `old('email', '')` or `old['email']`.

    Laravel's `old()` is a function, and templates ported across call it that
    way; the mapping interface is there so `'email' in old` also works.
    """

    def __init__(self, values=None):
        self._values = dict(values or {})

    def __call__(self, key=None, default=None):
        if key is None:
            return dict(self._values)

        value = self._values.get(key, default)

        return default if value is None else value

    def __getitem__(self, key):
        return self._values[key]

    def get(self, key, default=None):
        return self._values.get(key, default)

    def __contains__(self, key):
        return key in self._values

    def __bool__(self):
        return bool(self._values)

    def __iter__(self):
        return iter(self._values)

    def items(self):
        return self._values.items()

    def __repr__(self):
        return "<old {}>".format(sorted(self._values))
