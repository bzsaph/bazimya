"""The session store.

Laravel's Session facade, with the same vocabulary — get/put/forget/flash, and
a token for CSRF. Data lives in storage/framework/sessions as one file per
session, which needs no database and works on shared hosting.

The session id travels in a cookie that is signed with APP_KEY, so a client
cannot invent one; the signature is checked before the file is ever opened.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time


class SessionStore:
    def __init__(self, handler, name="bazimya_session", lifetime=120):
        self.handler = handler
        self.name = name
        self.lifetime = int(lifetime)

        self.id = None
        self._attributes = {}
        self._started = False
        self._dirty = False

    # -- lifecycle --------------------------------------------------------

    def start(self, session_id=None):
        self.id = session_id or self.generate_id()
        self._attributes = self.handler.read(self.id) or {}
        self._started = True

        # Anything flashed by the previous request has now been read once; it
        # is carried for exactly this request and then dropped.
        self._age_flash_data()

        if "_token" not in self._attributes:
            self.regenerate_token()

        return self

    def save(self):
        """Persist the session. Returns False when the write failed.

        Worth checking: a session that cannot be written means every request
        gets a fresh CSRF token, so every form POST fails with a 419 and
        nothing says why.
        """
        if not self._started:
            return False

        written = self.handler.write(self.id, self._attributes)
        self._dirty = False

        return bool(written)

    def started(self):
        return self._started

    def regenerate(self, destroy=True):
        """New id, same data — call this on login to stop session fixation."""
        old = self.id

        if destroy and old:
            self.handler.destroy(old)

        self.id = self.generate_id()
        self._dirty = True

        return self

    def invalidate(self):
        """Empty the session and give it a new id — for logout."""
        self._attributes = {}
        self.regenerate()
        self.regenerate_token()

        return self

    @staticmethod
    def generate_id():
        return secrets.token_hex(20)

    # -- reading and writing ----------------------------------------------

    def all(self):
        return {k: v for k, v in self._attributes.items() if not k.startswith("_flash")}

    def get(self, key, default=None):
        return self._attributes.get(key, default)

    def put(self, key, value=None):
        if isinstance(key, dict):
            self._attributes.update(key)
        else:
            self._attributes[key] = value

        self._dirty = True

        return self

    def has(self, key):
        return self._attributes.get(key) is not None

    def exists(self, key):
        return key in self._attributes

    def pull(self, key, default=None):
        value = self.get(key, default)
        self.forget(key)

        return value

    def forget(self, *keys):
        for key in keys:
            self._attributes.pop(key, None)

        self._dirty = True

        return self

    def flush(self):
        token = self._attributes.get("_token")
        self._attributes = {}

        if token:
            self._attributes["_token"] = token

        self._dirty = True

        return self

    def increment(self, key, amount=1):
        value = int(self.get(key, 0) or 0) + amount
        self.put(key, value)

        return value

    def decrement(self, key, amount=1):
        return self.increment(key, -amount)

    # -- flash data -------------------------------------------------------

    def flash(self, key, value=None):
        """Keep a value for the next request only — the redirect-and-show
        pattern behind 'status' messages and validation errors."""
        self.put(key, value)

        new = set(self._attributes.get("_flash_new", []))
        new.add(key)
        self._attributes["_flash_new"] = list(new)

        old = set(self._attributes.get("_flash_old", []))
        old.discard(key)
        self._attributes["_flash_old"] = list(old)

        self._dirty = True

        return self

    def reflash(self):
        """Keep the current flash data for one more request."""
        old = self._attributes.get("_flash_old", [])
        new = set(self._attributes.get("_flash_new", []))
        self._attributes["_flash_new"] = list(new.union(old))
        self._attributes["_flash_old"] = []

        return self

    def keep(self, *keys):
        new = set(self._attributes.get("_flash_new", []))
        new.update(keys)
        self._attributes["_flash_new"] = list(new)

        old = set(self._attributes.get("_flash_old", []))
        self._attributes["_flash_old"] = list(old.difference(keys))

        return self

    def _age_flash_data(self):
        # What was flashed last request is readable now and gone next request.
        for key in self._attributes.get("_flash_old", []):
            self._attributes.pop(key, None)

        self._attributes["_flash_old"] = list(self._attributes.get("_flash_new", []))
        self._attributes["_flash_new"] = []

    # -- validation errors and old input ----------------------------------

    def flash_input(self, values):
        return self.flash("_old_input", dict(values or {}))

    def old(self, key=None, default=None):
        values = self.get("_old_input", {}) or {}

        return values if key is None else values.get(key, default)

    def flash_errors(self, errors):
        return self.flash("_errors", dict(errors or {}))

    def errors(self):
        return self.get("_errors", {}) or {}

    # -- CSRF -------------------------------------------------------------

    def token(self):
        return self._attributes.get("_token")

    def regenerate_token(self):
        self._attributes["_token"] = secrets.token_urlsafe(32)
        self._dirty = True

        return self

    # -- cookie signing ---------------------------------------------------

    @staticmethod
    def sign(session_id, key):
        """Sign the id so a forged cookie is rejected before touching disk."""
        signature = hmac.new(
            _key_bytes(key), session_id.encode("utf-8"), hashlib.sha256
        ).digest()

        return session_id + "." + base64.urlsafe_b64encode(signature).decode().rstrip("=")

    @staticmethod
    def unsign(value, key):
        """Return the id, or None when the signature does not check out."""
        if not value or "." not in value:
            return None

        session_id, _, provided = value.rpartition(".")

        if not session_id:
            return None

        expected = SessionStore.sign(session_id, key).rpartition(".")[2]

        # compare_digest, not ==, so the comparison does not leak the position
        # of the first differing byte through timing.
        return session_id if hmac.compare_digest(expected, provided) else None


def _key_bytes(key):
    return (key or "bazimya-insecure-default").encode("utf-8")


class FileSessionHandler:
    """One JSON file per session under storage/framework/sessions."""

    def __init__(self, path, lifetime=120):
        self.path = path
        self.lifetime = int(lifetime)

    def _file(self, session_id):
        # The id is hex from our own generator, but it arrives from a cookie,
        # so it is hashed rather than trusted as a filename.
        safe = hashlib.sha256(session_id.encode("utf-8")).hexdigest()

        return os.path.join(self.path, safe)

    def read(self, session_id):
        path = self._file(session_id)

        try:
            if os.path.getmtime(path) + self.lifetime * 60 < time.time():
                self.destroy(session_id)

                return {}

            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)

            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def write(self, session_id, data):
        try:
            os.makedirs(self.path, exist_ok=True)
            path = self._file(session_id)
            temporary = "{}.{}.tmp".format(path, os.getpid())

            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(data, handle, default=str)

            os.replace(temporary, path)

            return True
        except (OSError, TypeError, ValueError):
            # A read-only storage/ should not take the site down; it means
            # sessions do not persist, which `bazimya doctor` reports.
            return False

    def destroy(self, session_id):
        try:
            os.remove(self._file(session_id))

            return True
        except OSError:
            return False

    def gc(self):
        """Delete expired session files. Called at random on a small fraction
        of requests, which is how Laravel does it too."""
        removed = 0
        deadline = time.time() - self.lifetime * 60

        try:
            entries = os.listdir(self.path)
        except OSError:
            return 0

        for entry in entries:
            path = os.path.join(self.path, entry)

            try:
                if os.path.getmtime(path) < deadline:
                    os.remove(path)
                    removed += 1
            except OSError:
                continue

        return removed


class ArraySessionHandler:
    """In-memory sessions. Used by the test harness, where persisting to disk
    between requests would only leak state across tests."""

    def __init__(self):
        self._data = {}

    def read(self, session_id):
        return dict(self._data.get(session_id, {}))

    def write(self, session_id, data):
        self._data[session_id] = dict(data)

        return True

    def destroy(self, session_id):
        self._data.pop(session_id, None)

        return True

    def gc(self):
        return 0
