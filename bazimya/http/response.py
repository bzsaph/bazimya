"""The outgoing HTTP response.

Handlers may return a Response, or a plain str/dict/list/None — `make` turns
any of those into one, so a controller that just returns a dict gets JSON
without saying so.
"""

import json as jsonlib
from datetime import datetime, timedelta, timezone
from http.cookies import SimpleCookie
from urllib.parse import quote

from ..support.aliases import AliasMeta, AliasMixin

STATUS_TEXT = {
    200: "OK",
    201: "Created",
    202: "Accepted",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    303: "See Other",
    304: "Not Modified",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    405: "Method Not Allowed",
    409: "Conflict",
    410: "Gone",
    419: "Page Expired",
    422: "Unprocessable Entity",
    429: "Too Many Requests",
    500: "Internal Server Error",
    501: "Not Implemented",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class Response(AliasMixin, metaclass=AliasMeta):
    def __init__(self, content="", status=200, headers=None):
        self.content = content
        self.status = int(status)
        self._headers = {}
        self._cookies = SimpleCookie()

        for name, value in (headers or {}).items():
            self.header(name, value)

    # -- constructors -----------------------------------------------------

    @classmethod
    def make(cls, value, status=200):
        """Normalise whatever a handler returned."""
        if isinstance(value, Response):
            return value

        if value is None:
            return cls("", 204)

        if isinstance(value, (dict, list, tuple)):
            return cls.json(list(value) if isinstance(value, tuple) else value, status)

        if isinstance(value, bool):
            return cls.json(value, status)

        if isinstance(value, bytes):
            return cls(value, status)

        return cls(str(value), status)

    @classmethod
    def json(cls, data, status=200, headers=None):
        response = cls(
            jsonlib.dumps(data, ensure_ascii=False, default=_json_default),
            status,
            headers,
        )
        response.header("Content-Type", "application/json; charset=utf-8")

        return response

    @classmethod
    def html(cls, content, status=200, headers=None):
        response = cls(content, status, headers)
        response.header("Content-Type", "text/html; charset=utf-8")

        return response

    @classmethod
    def text(cls, content, status=200, headers=None):
        response = cls(content, status, headers)
        response.header("Content-Type", "text/plain; charset=utf-8")

        return response

    @classmethod
    def redirect(cls, location, status=302):
        response = cls("", status)
        response.header("Location", location)

        return response

    @classmethod
    def no_content(cls, status=204):
        return cls("", status)

    @classmethod
    def download(cls, path, name=None, content_type="application/octet-stream"):
        with open(path, "rb") as handle:
            content = handle.read()

        import os

        name = name or os.path.basename(path)
        response = cls(content, 200)
        response.header("Content-Type", content_type)
        response.header(
            "Content-Disposition",
            "attachment; filename=\"{}\"; filename*=UTF-8''{}".format(
                name.replace('"', ""), quote(name)
            ),
        )

        return response

    # -- fluent modifiers -------------------------------------------------

    def header(self, name, value):
        self._headers[str(name)] = str(value)

        return self

    def with_headers(self, headers):
        for name, value in (headers or {}).items():
            self.header(name, value)

        return self

    def set_status(self, status):
        self.status = int(status)

        return self

    def cookie(
        self,
        name,
        value,
        minutes=None,
        path="/",
        domain=None,
        secure=False,
        http_only=True,
        same_site="Lax",
    ):
        self._cookies[name] = value
        cookie = self._cookies[name]
        cookie["path"] = path

        if minutes is not None:
            expires = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            cookie["expires"] = expires.strftime("%a, %d-%b-%Y %H:%M:%S GMT")
            cookie["max-age"] = int(minutes * 60)

        if domain:
            cookie["domain"] = domain

        cookie["secure"] = bool(secure)
        cookie["httponly"] = bool(http_only)

        if same_site:
            cookie["samesite"] = same_site

        return self

    def forget_cookie(self, name, path="/"):
        return self.cookie(name, "", minutes=-2628000, path=path)

    # -- sending ----------------------------------------------------------

    def body_bytes(self):
        if isinstance(self.content, bytes):
            return self.content

        return str(self.content).encode("utf-8")

    def header_list(self):
        """Headers as WSGI wants them: a list of (name, value) pairs."""
        body = self.body_bytes()
        headers = dict(self._headers)

        headers.setdefault("Content-Type", "text/html; charset=utf-8")

        # 204 and 304 must not carry a body or its length.
        if self.status in (204, 304):
            headers.pop("Content-Type", None)
            headers.pop("Content-Length", None)
        else:
            headers["Content-Length"] = str(len(body))

        pairs = [(name, value) for name, value in headers.items()]

        # Several Set-Cookie headers are legal and necessary, which a dict
        # cannot express — hence appending them separately.
        for morsel in self._cookies.values():
            pairs.append(("Set-Cookie", morsel.OutputString()))

        return pairs

    def status_line(self):
        return "{} {}".format(self.status, STATUS_TEXT.get(self.status, "Unknown"))

    def __repr__(self):
        return "<Response {}>".format(self.status_line())


def _json_default(value):
    """Serialise the objects that routinely reach a JSON response."""
    if isinstance(value, (datetime,)):
        return value.isoformat()

    if hasattr(value, "to_dict"):
        return value.to_dict()

    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}

    return str(value)
