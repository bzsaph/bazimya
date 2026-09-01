"""The incoming HTTP request.

Built from a WSGI environ, so the same object serves the development server,
gunicorn on a VPS and Passenger on shared hosting. The API follows Laravel's
Request, because that is the vocabulary this framework is written in.
"""

import json as jsonlib
from email.parser import BytesParser
from email.policy import default as email_policy
from urllib.parse import parse_qs, unquote

from ..support.aliases import AliasMixin

#: Bodies larger than this are not buffered for urlencoded/JSON parsing.
MAX_FORM_BODY = 8 * 1024 * 1024

#: Multipart bodies are parsed in memory, so uploads have their own ceiling.
#: Raise it in config if you accept large files — and prefer streaming them
#: straight to storage if you accept very large ones.
MAX_MULTIPART_BODY = 32 * 1024 * 1024


class UploadedFile:
    """One file from a multipart form."""

    def __init__(self, name, content_type, content):
        self.name = name
        self.content_type = content_type
        self._content = content or b""

    def read(self):
        return self._content

    def save(self, path):
        with open(path, "wb") as handle:
            handle.write(self._content)

        return path

    def size(self):
        return len(self._content)

    def extension(self):
        return self.name.rsplit(".", 1)[-1].lower() if self.name and "." in self.name else ""

    def __repr__(self):
        return "<UploadedFile {} {} bytes>".format(self.name, self.size())


class Request(AliasMixin):
    def __init__(
        self,
        method="GET",
        path="/",
        query=None,
        body=None,
        headers=None,
        cookies=None,
        files=None,
        raw=b"",
        environ=None,
    ):
        self._method = str(method).upper()
        self._path = path or "/"
        self._query = query or {}
        self._body = body or {}
        self._headers = {str(k).lower(): v for k, v in (headers or {}).items()}
        self._cookies = cookies or {}
        self._files = files or {}
        self._raw = raw or b""
        self.environ = environ or {}
        self._route_parameters = {}
        self._attributes = {}

    # -- construction -----------------------------------------------------

    @classmethod
    def from_environ(cls, environ):
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = unquote(environ.get("PATH_INFO", "/") or "/")

        headers = cls._headers_from_environ(environ)
        query = cls._flatten(parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=True))

        raw, body, files = cls._read_body(environ, headers, method)

        # Let an HTML form spoof PUT/PATCH/DELETE, exactly as @method does in
        # Laravel — browsers still only send GET and POST.
        if method == "POST" and isinstance(body, dict):
            spoofed = str(body.get("_method", "")).upper()

            if spoofed in ("PUT", "PATCH", "DELETE"):
                method = spoofed

        return cls(
            method=method,
            path=path,
            query=query,
            body=body,
            headers=headers,
            cookies=cls._cookies_from(headers.get("cookie", "")),
            files=files,
            raw=raw,
            environ=environ,
        )

    @staticmethod
    def _headers_from_environ(environ):
        headers = {}

        for key, value in environ.items():
            if key.startswith("HTTP_"):
                headers[key[5:].replace("_", "-").lower()] = value

        for key, header in (("CONTENT_TYPE", "content-type"), ("CONTENT_LENGTH", "content-length")):
            if environ.get(key):
                headers[header] = environ[key]

        return headers

    @classmethod
    def _read_body(cls, environ, headers, method):
        content_type = headers.get("content-type", "") or ""
        length = headers.get("content-length") or 0

        try:
            length = int(length)
        except (TypeError, ValueError):
            length = 0

        stream = environ.get("wsgi.input")

        if stream is None or length <= 0 or method in ("GET", "HEAD", "OPTIONS"):
            return b"", {}, {}

        if "multipart/form-data" in content_type:
            if length > MAX_MULTIPART_BODY:
                return b"", {}, {}

            body, files = cls._parse_multipart(stream.read(length) or b"", content_type)

            # The raw bytes of an upload are not worth keeping around; the
            # parsed files already hold everything.
            return b"", body, files

        if length > MAX_FORM_BODY:
            # Refusing to buffer is better than an out-of-memory kill on a
            # shared host with a small memory cap.
            return b"", {}, {}

        raw = stream.read(length) or b""

        if "application/json" in content_type:
            try:
                decoded = jsonlib.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                decoded = {}

            return raw, decoded if isinstance(decoded, dict) else {"_json": decoded}, {}

        if "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(raw.decode("utf-8", "replace"), keep_blank_values=True)

            return raw, cls._flatten(parsed), {}

        return raw, {}, {}

    @staticmethod
    def _parse_multipart(raw, content_type):
        """Parse a multipart body with the email package.

        The `cgi` module used to do this, but it was removed in Python 3.13,
        and `email` is the replacement the standard library points at.
        """
        body = {}
        files = {}

        if not raw:
            return body, files

        # email needs the Content-Type header (it carries the boundary) in
        # front of the body to parse it as a MIME document.
        document = (
            b"Content-Type: " + content_type.encode("utf-8", "replace") + b"\r\n"
            b"MIME-Version: 1.0\r\n\r\n" + raw
        )

        try:
            message = BytesParser(policy=email_policy).parsebytes(document)
        except Exception:  # noqa: BLE001 — a malformed body is a client error
            return body, files

        if not message.is_multipart():
            return body, files

        for part in message.iter_parts():
            name = part.get_param("name", header="content-disposition")

            if not name:
                continue

            filename = part.get_filename()
            payload = part.get_payload(decode=True)

            if filename:
                files.setdefault(name, []).append(
                    UploadedFile(filename, part.get_content_type(), payload)
                )
            else:
                body[name] = (payload or b"").decode("utf-8", "replace")

        # One file per field is the common case; only expose a list when the
        # form really sent several.
        files = {k: (v[0] if len(v) == 1 else v) for k, v in files.items()}

        return body, files

    @staticmethod
    def _flatten(parsed):
        """parse_qs gives every value as a list; keep the last unless the name
        ends in [], which is how HTML forms mean "several"."""
        flat = {}

        for key, values in parsed.items():
            if key.endswith("[]"):
                flat[key[:-2]] = values
            else:
                flat[key] = values[-1] if values else ""

        return flat

    @staticmethod
    def _cookies_from(header):
        cookies = {}

        for chunk in str(header or "").split(";"):
            if "=" in chunk:
                name, _, value = chunk.partition("=")
                cookies[name.strip()] = unquote(value.strip())

        return cookies

    # -- basics -----------------------------------------------------------

    def method(self):
        return self._method

    def is_method(self, method):
        return self._method == str(method).upper()

    def path(self):
        path = "/" + str(self._path).strip("/")

        return "/" if path == "/" else path.rstrip("/")

    def url(self):
        scheme = self.scheme()
        host = self.header("host") or self.environ.get("SERVER_NAME", "localhost")

        return "{}://{}{}".format(scheme, host, self._path)

    def full_url(self):
        query = self.environ.get("QUERY_STRING", "")

        return self.url() + ("?" + query if query else "")

    def scheme(self):
        forwarded = str(self.header("x-forwarded-proto", "") or "").split(",")[0].strip()

        if forwarded:
            return forwarded

        return self.environ.get("wsgi.url_scheme", "http")

    def is_secure(self):
        return self.scheme() == "https"

    def ip(self):
        forwarded = str(self.header("x-forwarded-for", "") or "")

        if forwarded:
            return forwarded.split(",")[0].strip()

        return self.environ.get("REMOTE_ADDR", "")

    # -- input ------------------------------------------------------------

    def input(self, key, default=None):
        """Body first, then query string — Laravel's precedence."""
        if key in self._body:
            return self._body[key]

        return self._query.get(key, default)

    def all(self):
        merged = dict(self._query)
        merged.update(self._body)

        return merged

    def only(self, *keys):
        source = self.all()

        return {key: source[key] for key in keys if key in source}

    def excluding(self, *keys):
        return {k: v for k, v in self.all().items() if k not in keys}

    def has(self, *keys):
        source = self.all()

        return all(key in source for key in keys)

    def filled(self, *keys):
        return all(self.input(key) not in (None, "", [], {}) for key in keys)

    def boolean(self, key, default=False):
        value = self.input(key, default)

        if isinstance(value, bool):
            return value

        return str(value).strip().lower() in ("1", "true", "on", "yes")

    def integer(self, key, default=0):
        try:
            return int(self.input(key, default))
        except (TypeError, ValueError):
            return default

    def query(self, key=None, default=None):
        if key is None:
            return dict(self._query)

        return self._query.get(key, default)

    def post(self):
        return dict(self._body)

    def json(self, key=None, default=None):
        try:
            decoded = jsonlib.loads(self._raw.decode("utf-8")) if self._raw else None
        except (ValueError, UnicodeDecodeError):
            decoded = None

        if key is None:
            return decoded if decoded is not None else default

        if isinstance(decoded, dict):
            return decoded.get(key, default)

        return default

    def raw(self):
        return self._raw

    def file(self, key, default=None):
        return self._files.get(key, default)

    def files(self):
        return dict(self._files)

    def has_file(self, key):
        return key in self._files

    # -- headers and cookies ----------------------------------------------

    def header(self, name, default=None):
        return self._headers.get(str(name).lower(), default)

    def headers(self):
        return dict(self._headers)

    def cookie(self, name, default=None):
        return self._cookies.get(name, default)

    def cookies(self):
        return dict(self._cookies)

    def bearer_token(self):
        header = str(self.header("authorization", "") or "")

        return header[7:].strip() if header.lower().startswith("bearer ") else None

    def is_json(self):
        return "json" in str(self.header("content-type", "") or "").lower()

    def wants_json(self):
        accept = str(self.header("accept", "") or "").lower()

        return "application/json" in accept or (self.is_json() and "text/html" not in accept)

    def is_ajax(self):
        return str(self.header("x-requested-with", "") or "").lower() == "xmlhttprequest"

    # -- route parameters -------------------------------------------------

    def set_route_parameters(self, parameters):
        self._route_parameters = dict(parameters)

    def route(self, key=None, default=None):
        if key is None:
            return dict(self._route_parameters)

        return self._route_parameters.get(key, default)

    def parameters(self):
        return dict(self._route_parameters)

    # -- per-request scratch space ----------------------------------------

    def set(self, key, value):
        """Somewhere for middleware to leave things for the controller, e.g.
        the authenticated user."""
        self._attributes[key] = value

        return self

    def get(self, key, default=None):
        return self._attributes.get(key, default)

    def session(self):
        """The session, once StartSession has run. None on routes without it."""
        return self._attributes.get("session")

    def user(self):
        """The authenticated user, once Authenticate (or any guard) has run."""
        return self._attributes.get("user")

    def is_authenticated(self):
        return self._attributes.get("user") is not None

    def __repr__(self):
        return "<Request {} {}>".format(self._method, self.path())
