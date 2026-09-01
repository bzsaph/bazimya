"""The test harness.

A base test case, with helpers for driving the app through WSGI:

    class ExampleTest(TestCase):
        def test_home_page(self):
            response = self.get('/')

            response.assert_ok()
            response.assert_see('Welcome')

Requests go straight through the WSGI application — no server, no sockets — so
a test suite runs at the speed of function calls.
"""

import io
import json as jsonlib
import os
import unittest
from urllib.parse import urlencode


class TestResponse:
    """A response, with assertions that say what went wrong."""

    def __init__(self, status, headers, body, request_path=""):
        self.status = int(str(status).split(" ")[0])
        self.status_line = status
        self.headers = dict(headers)
        self.body = body
        self.request_path = request_path

    # -- reading ----------------------------------------------------------

    def json(self, key=None, default=None):
        try:
            decoded = jsonlib.loads(self.body)
        except ValueError:
            raise AssertionError(
                "The response is not JSON.\n\n{}".format(self._excerpt())
            ) from None

        if key is None:
            return decoded

        value = decoded

        for segment in str(key).split("."):
            if not isinstance(value, dict) or segment not in value:
                return default

            value = value[segment]

        return value

    def header(self, name, default=None):
        for key, value in self.headers.items():
            if key.lower() == str(name).lower():
                return value

        return default

    # -- assertions -------------------------------------------------------

    def assert_status(self, expected):
        assert self.status == expected, (
            "Expected status {} from {}, got {}.\n\n{}".format(
                expected, self.request_path, self.status_line, self._excerpt()
            )
        )

        return self

    def assert_ok(self):
        return self.assert_status(200)

    def assert_created(self):
        return self.assert_status(201)

    def assert_no_content(self):
        return self.assert_status(204)

    def assert_not_found(self):
        return self.assert_status(404)

    def assert_forbidden(self):
        return self.assert_status(403)

    def assert_unauthorized(self):
        return self.assert_status(401)

    def assert_successful(self):
        assert 200 <= self.status < 300, (
            "Expected a 2xx from {}, got {}.\n\n{}".format(
                self.request_path, self.status_line, self._excerpt()
            )
        )

        return self

    def assert_redirect(self, to=None):
        assert 300 <= self.status < 400, "Expected a redirect, got {}.".format(
            self.status_line
        )

        if to is not None:
            location = self.header("Location")
            assert location == to, "Expected a redirect to {}, got {}.".format(to, location)

        return self

    def assert_see(self, text, escaped=True):
        import html as html_module

        needle = html_module.escape(str(text), quote=True) if escaped else str(text)

        assert needle in self.body or str(text) in self.body, (
            "Did not find {!r} in the response from {}.\n\n{}".format(
                text, self.request_path, self._excerpt()
            )
        )

        return self

    def assert_dont_see(self, text):
        assert str(text) not in self.body, (
            "Found {!r} in the response from {}, and should not have.".format(
                text, self.request_path
            )
        )

        return self

    def assert_json(self, expected):
        actual = self.json()

        for key, value in expected.items():
            assert key in actual, "Key {!r} is missing from the JSON.\n\n{}".format(
                key, self._excerpt()
            )
            assert actual[key] == value, (
                "Expected {!r} to be {!r}, got {!r}.".format(key, value, actual[key])
            )

        return self

    def assert_json_path(self, path, value):
        actual = self.json(path)
        assert actual == value, "Expected {} to be {!r}, got {!r}.".format(path, value, actual)

        return self

    def assert_header(self, name, value=None):
        actual = self.header(name)
        assert actual is not None, "Header {!r} is missing.".format(name)

        if value is not None:
            assert actual == value, "Expected {}: {!r}, got {!r}.".format(name, value, actual)

        return self

    def _excerpt(self, limit=800):
        body = self.body.strip()

        if len(body) > limit:
            body = body[:limit] + "\n… (truncated)"

        return "--- response body ---\n{}\n---------------------".format(body or "(empty)")

    def __repr__(self):
        return "<TestResponse {}>".format(self.status_line)


class TestCase(unittest.TestCase):
    """Base class for feature tests.

    The application is created once per test method and torn down after, so no
    state leaks between tests.
    """

    #: Set to a path to test a different project.
    base_path = None

    #: Run migrations before each test, against an in-memory database.
    refresh_database = True

    def setUp(self):
        os.environ.setdefault("APP_ENV", "testing")

        self.app = self.create_application()
        self._cookies = {}

        if self.refresh_database:
            self.migrate()

        self.app.boot()

    def tearDown(self):
        from .foundation.application import Application

        connection = self.app.make("db")
        connection.close()
        Application.set_instance(None)

    def create_application(self):
        from .foundation.application import Application

        base = self.base_path or os.getcwd()
        application = Application(base)

        # Tests get an in-memory database and in-memory sessions and cache, so
        # nothing they do touches the developer's real data or files.
        config = application.make("config")
        config.set("database.default", "sqlite")
        config.set("database.connections.sqlite.database", ":memory:")
        config.set("session.driver", "array")
        config.set("cache.default", "array")
        config.set("mail.default", "array")
        config.set("app.debug", True)

        return application

    def migrate(self):
        from .database.migration import Migrator

        Migrator(self.app.make("db"), self.app.migration_paths()).run()

        return self

    # -- making requests --------------------------------------------------

    def get(self, path, headers=None):
        return self.request("GET", path, headers=headers)

    def post(self, path, data=None, headers=None):
        return self.request("POST", path, data=data, headers=headers)

    def put(self, path, data=None, headers=None):
        return self.request("PUT", path, data=data, headers=headers)

    def patch(self, path, data=None, headers=None):
        return self.request("PATCH", path, data=data, headers=headers)

    def delete(self, path, data=None, headers=None):
        return self.request("DELETE", path, data=data, headers=headers)

    def get_json(self, path, headers=None):
        return self.get(path, _json_headers(headers))

    def post_json(self, path, data=None, headers=None):
        return self.request("POST", path, json=data, headers=_json_headers(headers))

    def request(self, method, path, data=None, json=None, headers=None):
        query = ""

        if "?" in path:
            path, _, query = path.partition("?")

        body = b""
        content_type = None

        if json is not None:
            body = jsonlib.dumps(json).encode("utf-8")
            content_type = "application/json"
        elif data is not None:
            body = urlencode(data, doseq=True).encode("utf-8")
            content_type = "application/x-www-form-urlencoded"

        environ = {
            "REQUEST_METHOD": method.upper(),
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "SERVER_NAME": "localhost",
            "SERVER_PORT": "80",
            "SERVER_PROTOCOL": "HTTP/1.1",
            "wsgi.url_scheme": "http",
            "wsgi.input": io.BytesIO(body),
            "CONTENT_LENGTH": str(len(body)),
            "HTTP_HOST": "localhost",
        }

        if content_type:
            environ["CONTENT_TYPE"] = content_type

        # Carry cookies between requests, so a login in one test survives into
        # the next request of that test.
        if self._cookies:
            environ["HTTP_COOKIE"] = "; ".join(
                "{}={}".format(k, v) for k, v in self._cookies.items()
            )

        for name, value in (headers or {}).items():
            key = "HTTP_" + name.upper().replace("-", "_")

            if name.lower() == "content-type":
                environ["CONTENT_TYPE"] = value
            else:
                environ[key] = value

        captured = {}

        def start_response(status, response_headers, exc_info=None):
            captured["status"] = status
            captured["headers"] = response_headers

        chunks = self.app(environ, start_response)
        body_out = b"".join(chunks).decode("utf-8", "replace")

        self._store_cookies(captured.get("headers", []))

        return TestResponse(
            captured.get("status", "500 Internal Server Error"),
            dict(captured.get("headers", [])),
            body_out,
            "{} {}".format(method.upper(), path),
        )

    def _store_cookies(self, headers):
        for name, value in headers:
            if name.lower() != "set-cookie":
                continue

            pair = value.split(";")[0]

            if "=" in pair:
                key, _, cookie_value = pair.partition("=")
                self._cookies[key.strip()] = cookie_value.strip()

    # -- helpers ----------------------------------------------------------

    def acting_as(self, user):
        """Log a user in for the requests that follow."""
        from .facades import Auth

        session = self.app.make("session")

        if not session.started():
            session.start()

        Auth.set_session(session)
        Auth.login(user)
        session.save()

        return self

    def assert_database_has(self, table, values):
        query = self.app.make("db").table(table)

        for column, value in values.items():
            query = query.where(column, value)

        assert query.exists(), "No row in [{}] matches {!r}.".format(table, values)

        return self

    def assert_database_missing(self, table, values):
        query = self.app.make("db").table(table)

        for column, value in values.items():
            query = query.where(column, value)

        assert not query.exists(), "A row in [{}] matches {!r}, and should not.".format(
            table, values
        )

        return self

    def assert_database_count(self, table, expected):
        actual = self.app.make("db").table(table).count()
        assert actual == expected, "Expected {} rows in [{}], found {}.".format(
            expected, table, actual
        )

        return self


def _json_headers(headers):
    merged = dict(headers or {})
    merged.setdefault("Accept", "application/json")

    return merged
