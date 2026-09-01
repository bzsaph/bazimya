"""Middleware.

The shape is `handle(request, next)`: either return a response of
its own, or calls `next(request)` and (optionally) works on what comes back.

    class EnsureToken(Middleware):
        def handle(self, request, next):
            if request.bearer_token() != 'secret':
                return Response.json({'error': 'Unauthorised'}, 401)

            return next(request)
"""

from .response import Response


class Middleware:
    def handle(self, request, next):
        raise NotImplementedError(
            "{} must implement handle(self, request, next).".format(type(self).__name__)
        )


class TrimStrings(Middleware):
    """Trim whitespace off incoming strings. Enabled by default."""

    skip = ("password", "password_confirmation")

    def handle(self, request, next):
        for source in (request._body, request._query):
            for key, value in list(source.items()):
                if isinstance(value, str) and key not in self.skip:
                    source[key] = value.strip()

        return next(request)


class ConvertEmptyStringsToNull(Middleware):
    """An empty form field means "not provided", not "the empty string"."""

    skip = ()

    def handle(self, request, next):
        for source in (request._body, request._query):
            for key, value in list(source.items()):
                if value == "" and key not in self.skip:
                    source[key] = None

        return next(request)


class SecurityHeaders(Middleware):
    """A small, uncontroversial set of response headers."""

    def handle(self, request, next):
        response = Response.make(next(request))

        response.header("X-Content-Type-Options", "nosniff")
        response.header("X-Frame-Options", "SAMEORIGIN")
        response.header("Referrer-Policy", "strict-origin-when-cross-origin")

        return response


class HandleCors(Middleware):
    """Permissive CORS for API routes. Narrow `allowed_origins` before you
    put anything behind authentication."""

    allowed_origins = ["*"]
    allowed_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allowed_headers = ["Content-Type", "Authorization", "X-Requested-With"]
    max_age = 3600

    def handle(self, request, next):
        if request.is_method("OPTIONS"):
            response = Response("", 204)
        else:
            response = Response.make(next(request))

        origin = request.header("origin")

        if origin and ("*" in self.allowed_origins or origin in self.allowed_origins):
            response.header(
                "Access-Control-Allow-Origin",
                "*" if "*" in self.allowed_origins else origin,
            )
            response.header("Access-Control-Allow-Methods", ", ".join(self.allowed_methods))
            response.header("Access-Control-Allow-Headers", ", ".join(self.allowed_headers))
            response.header("Access-Control-Max-Age", str(self.max_age))

            if "*" not in self.allowed_origins:
                response.header("Vary", "Origin")

        return response
