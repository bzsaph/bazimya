"""The development server.

A threaded wsgiref server, plus two things wsgiref does not do: serving files
out of public/, and restarting when source changes.

Production does not use any of this — there, Passenger or gunicorn imports the
WSGI callable directly.
"""

import mimetypes
import os
import socket
import subprocess
import sys
import threading
import time
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIRequestHandler, WSGIServer, make_server

#: Files under public/ are served directly; everything else is the app's.
CACHE_CONTROL = "public, max-age=0, must-revalidate"


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True
    allow_reuse_address = True


class QuietHandler(WSGIRequestHandler):
    """Logs one tidy line per request instead of wsgiref's default format."""

    def log_message(self, format, *args):  # noqa: A002 — matches the base class
        sys.stdout.write(
            "  {}  {}\n".format(time.strftime("%H:%M:%S"), format % args)
        )
        sys.stdout.flush()

    def log_error(self, format, *args):  # noqa: A002
        sys.stderr.write("  {}  {}\n".format(time.strftime("%H:%M:%S"), format % args))


class StaticFiles:
    """Serve public/ in front of the application.

    Apache and nginx do this in production; the dev server has to do it
    itself, and it has to refuse to walk out of public/ while doing so.
    """

    def __init__(self, application, directory):
        self.application = application
        self.directory = os.path.abspath(directory)

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "/")

        if path not in ("", "/"):
            resolved = self._resolve(path)

            if resolved:
                return self._serve(resolved, start_response)

        return self.application(environ, start_response)

    def _resolve(self, path):
        candidate = os.path.normpath(os.path.join(self.directory, path.lstrip("/")))

        # ../ in a URL must not escape public/.
        if not candidate.startswith(self.directory + os.sep):
            return None

        return candidate if os.path.isfile(candidate) else None

    def _serve(self, path, start_response):
        content_type, encoding = mimetypes.guess_type(path)

        with open(path, "rb") as handle:
            body = handle.read()

        headers = [
            ("Content-Type", content_type or "application/octet-stream"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", CACHE_CONTROL),
        ]

        if encoding:
            headers.append(("Content-Encoding", encoding))

        start_response("200 OK", headers)

        return [body]


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------


def port_is_free(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.3)

        return probe.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", port)) != 0


def first_free_port(host, port, attempts=20):
    """Step forward rather than dying on a port someone else is using."""
    for candidate in range(port, port + attempts):
        if port_is_free(host, candidate):
            return candidate

    return port


# ---------------------------------------------------------------------------
# Reloading
# ---------------------------------------------------------------------------

RELOAD_ENVIRONMENT = "BAZIMYA_RELOADER_CHILD"

WATCHED_SUFFIXES = (".py", ".baz.html", ".env")

IGNORED_DIRECTORIES = {
    "__pycache__",
    ".git",
    "node_modules",
    "storage",
    "build",
    ".venv",
    "venv",
    ".pytest_cache",
}


def iter_watched_files(root):
    for directory, subdirectories, files in os.walk(root):
        subdirectories[:] = [
            d for d in subdirectories if d not in IGNORED_DIRECTORIES and not d.startswith(".")
        ]

        for name in files:
            if name.endswith(WATCHED_SUFFIXES) or name == ".env":
                yield os.path.join(directory, name)


def snapshot(root):
    state = {}

    for path in iter_watched_files(root):
        try:
            state[path] = os.path.getmtime(path)
        except OSError:
            continue

    return state


def run_with_reloader(root, interval=1.0):
    """Run this command again in a child process, restarting it on change.

    The parent only watches; the child is the server. That way a syntax error
    kills the child, the parent notices the file change that follows, and the
    server comes back — which is the behaviour you want while editing.
    """
    environment = dict(os.environ)
    environment[RELOAD_ENVIRONMENT] = "1"

    command = [sys.executable] + sys.argv
    process = subprocess.Popen(command, env=environment)
    previous = snapshot(root)

    try:
        while True:
            time.sleep(interval)

            if process.poll() is not None:
                # The child exited on its own. If it crashed, wait for an edit
                # and restart; if it exited cleanly, stop.
                if process.returncode == 0:
                    return 0

                changed = _wait_for_change(root, previous, interval)
                previous = changed
                process = subprocess.Popen(command, env=environment)
                continue

            current = snapshot(root)

            if current != previous:
                previous = current
                sys.stdout.write("\n  Reloading...\n")
                sys.stdout.flush()

                process.terminate()

                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()

                process = subprocess.Popen(command, env=environment)
    except KeyboardInterrupt:
        process.terminate()

        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

        return 0


def _wait_for_change(root, previous, interval):
    while True:
        time.sleep(interval)
        current = snapshot(root)

        if current != previous:
            return current


def is_reloader_child():
    return os.environ.get(RELOAD_ENVIRONMENT) == "1"


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------


def serve(application, host="127.0.0.1", port=8000, public_directory=None, on_start=None):
    if public_directory and os.path.isdir(public_directory):
        application = StaticFiles(application, public_directory)

    server = make_server(host, port, application, ThreadedWSGIServer, QuietHandler)

    if on_start:
        on_start(host, port)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        sys.stdout.write("\n")
    finally:
        server.shutdown()
        server.server_close()

    return 0
