"""Authentication middleware — Authenticate and RedirectIfAuthenticated."""

from ..http.exceptions import Unauthorized
from ..http.middleware import Middleware
from ..http.response import Response


class Authenticate(Middleware):
    """Stop guests. Registered as the `auth` alias.

    Browsers get a redirect to the login page; anything asking for JSON gets a
    401, because redirecting an API client to an HTML form is never useful.
    """

    redirect_to = "/login"

    def handle(self, request, next):
        from ..facades import Auth

        session = request.get("session")

        if session is not None:
            Auth.set_session(session)

        user = Auth.user()

        if user is None:
            if request.wants_json():
                raise Unauthorized("Unauthenticated.")

            if session is not None:
                # Remember where they were headed, so login can send them back.
                session.put("_intended", request.full_url())

            return Response.redirect(self.redirect_to)

        request.set("user", user)

        return next(request)


class RedirectIfAuthenticated(Middleware):
    """Keep logged-in users off the login and register pages. Alias: `guest`."""

    redirect_to = "/"

    def handle(self, request, next):
        from ..facades import Auth

        session = request.get("session")

        if session is not None:
            Auth.set_session(session)

        if Auth.check():
            return Response.redirect(self.redirect_to)

        return next(request)


class ResolveUser(Middleware):
    """Attach the authenticated user to the request without requiring one.

    For pages that show a name when signed in and a login link otherwise.
    """

    def handle(self, request, next):
        from ..facades import Auth

        session = request.get("session")

        if session is not None:
            Auth.set_session(session)
            request.set("user", Auth.user())

        return next(request)
