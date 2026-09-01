"""HTTP exceptions.

Raising one of these from anywhere in a request produces the right status code
instead of a 500 — the equivalent of Laravel's abort().
"""


class HttpException(Exception):
    status = 500

    def __init__(self, message="", status=None, headers=None):
        self.status = int(status if status is not None else self.status)
        self.headers = dict(headers or {})
        super().__init__(message or self.default_message())

    def default_message(self):
        from .response import STATUS_TEXT

        return STATUS_TEXT.get(self.status, "Error")


class BadRequest(HttpException):
    status = 400


class Unauthorized(HttpException):
    status = 401


class Forbidden(HttpException):
    status = 403


class NotFound(HttpException):
    status = 404


class MethodNotAllowed(HttpException):
    status = 405


class PageExpired(HttpException):
    """CSRF token missing or wrong — Laravel's 419."""

    status = 419


class ValidationException(HttpException):
    status = 422

    def __init__(self, errors=None, message="The given data was invalid."):
        self.errors = dict(errors or {})
        super().__init__(message, 422)


class TooManyRequests(HttpException):
    status = 429


class ServerError(HttpException):
    status = 500


class ServiceUnavailable(HttpException):
    status = 503


def abort(status, message=""):
    """abort(404) / abort(403, 'Not yours')."""
    mapping = {
        400: BadRequest,
        401: Unauthorized,
        403: Forbidden,
        404: NotFound,
        405: MethodNotAllowed,
        419: PageExpired,
        422: ValidationException,
        429: TooManyRequests,
        503: ServiceUnavailable,
    }

    exception = mapping.get(status)

    if exception is ValidationException:
        raise ValidationException(message=message or "The given data was invalid.")

    if exception is not None:
        raise exception(message)

    raise HttpException(message, status)


def abort_if(condition, status, message=""):
    if condition:
        abort(status, message)


def abort_unless(condition, status, message=""):
    if not condition:
        abort(status, message)
