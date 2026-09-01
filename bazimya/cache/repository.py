"""The cache.

Laravel's Cache facade, with a file store under storage/framework/cache. No
Redis, no Memcached — the file store needs nothing installed, which is the
whole point on shared hosting.

    Cache.put('key', value, seconds=600)
    Cache.get('key', default)
    Cache.remember('key', 600, lambda: expensive())
"""

import hashlib
import json
import os
import time


class FileStore:
    def __init__(self, directory):
        self.directory = directory

    def _file(self, key):
        safe = hashlib.sha256(str(key).encode("utf-8")).hexdigest()

        # Two levels of subdirectory, so a large cache does not put tens of
        # thousands of files in one directory.
        return os.path.join(self.directory, safe[:2], safe[2:4], safe)

    def get(self, key, default=None):
        path = self._file(key)

        try:
            with open(path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, ValueError):
            return default

        expires = payload.get("expires")

        if expires is not None and expires < time.time():
            self.forget(key)

            return default

        return payload.get("value", default)

    def put(self, key, value, seconds=None):
        path = self._file(key)

        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)

            payload = {
                "value": value,
                "expires": time.time() + seconds if seconds else None,
            }

            temporary = "{}.{}.tmp".format(path, os.getpid())

            with open(temporary, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, default=str)

            os.replace(temporary, path)

            return True
        except (OSError, TypeError, ValueError):
            # A cache that cannot write is slow, not broken.
            return False

    def forget(self, key):
        try:
            os.remove(self._file(key))

            return True
        except OSError:
            return False

    def flush(self):
        import shutil

        try:
            shutil.rmtree(self.directory)
            os.makedirs(self.directory, exist_ok=True)

            return True
        except OSError:
            return False


class ArrayStore:
    """In-memory, per-process. The default while testing."""

    def __init__(self):
        self._items = {}

    def get(self, key, default=None):
        entry = self._items.get(key)

        if entry is None:
            return default

        value, expires = entry

        if expires is not None and expires < time.time():
            self._items.pop(key, None)

            return default

        return value

    def put(self, key, value, seconds=None):
        self._items[key] = (value, time.time() + seconds if seconds else None)

        return True

    def forget(self, key):
        return self._items.pop(key, None) is not None

    def flush(self):
        self._items = {}

        return True


class NullStore:
    """Stores nothing. Useful for turning caching off without code changes."""

    def get(self, key, default=None):
        return default

    def put(self, key, value, seconds=None):
        return True

    def forget(self, key):
        return True

    def flush(self):
        return True


class CacheRepository:
    def __init__(self, store):
        self.store = store

    def get(self, key, default=None):
        return self.store.get(key, default)

    def put(self, key, value, seconds=None):
        return self.store.put(key, value, seconds)

    def add(self, key, value, seconds=None):
        """Store it only if it is not there already."""
        sentinel = object()

        if self.store.get(key, sentinel) is not sentinel:
            return False

        return self.store.put(key, value, seconds)

    def forever(self, key, value):
        return self.store.put(key, value, None)

    def has(self, key):
        sentinel = object()

        return self.store.get(key, sentinel) is not sentinel

    def missing(self, key):
        return not self.has(key)

    def pull(self, key, default=None):
        value = self.get(key, default)
        self.forget(key)

        return value

    def remember(self, key, seconds, callback):
        """Return the cached value, computing and storing it when absent."""
        sentinel = object()
        value = self.store.get(key, sentinel)

        if value is not sentinel:
            return value

        value = callback()
        self.store.put(key, value, seconds)

        return value

    def remember_forever(self, key, callback):
        return self.remember(key, None, callback)

    def increment(self, key, amount=1):
        value = int(self.get(key, 0) or 0) + amount
        self.forever(key, value)

        return value

    def decrement(self, key, amount=1):
        return self.increment(key, -amount)

    def forget(self, key):
        return self.store.forget(key)

    def flush(self):
        return self.store.flush()
