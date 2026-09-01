"""File storage.

The Storage facade over local disks. Two are configured by default:
`local` (storage/app, private) and `public` (storage/app/public, served).

    Storage.put('reports/june.csv', data)
    Storage.get('reports/june.csv')
    Storage.disk('public').url('avatars/1.png')
"""

import os
import shutil


class LocalDisk:
    def __init__(self, root, url=None, visibility="private"):
        self.root = os.path.abspath(root)
        self.url_prefix = url
        self.visibility = visibility

    # -- paths ------------------------------------------------------------

    def path(self, relative):
        """Resolve a path inside the disk, refusing to escape it.

        Paths often come from user input, and `../` in one of them is how a
        file store turns into arbitrary read/write of the filesystem.
        """
        candidate = os.path.normpath(os.path.join(self.root, str(relative).lstrip("/")))

        if candidate != self.root and not candidate.startswith(self.root + os.sep):
            raise ValueError(
                "Path [{}] resolves outside the disk root.".format(relative)
            )

        return candidate

    def url(self, relative):
        if not self.url_prefix:
            raise ValueError(
                "This disk has no url configured, so it cannot build public URLs."
            )

        return self.url_prefix.rstrip("/") + "/" + str(relative).lstrip("/")

    # -- reading ----------------------------------------------------------

    def exists(self, relative):
        return os.path.exists(self.path(relative))

    def missing(self, relative):
        return not self.exists(relative)

    def get(self, relative, default=None):
        try:
            with open(self.path(relative), "rb") as handle:
                return handle.read()
        except OSError:
            return default

    def get_text(self, relative, default=None, encoding="utf-8"):
        raw = self.get(relative)

        return default if raw is None else raw.decode(encoding, "replace")

    def size(self, relative):
        return os.path.getsize(self.path(relative))

    def last_modified(self, relative):
        return os.path.getmtime(self.path(relative))

    def files(self, directory="", recursive=False):
        base = self.path(directory)

        if not os.path.isdir(base):
            return []

        found = []

        if recursive:
            for root, _, names in os.walk(base):
                for name in names:
                    found.append(
                        os.path.relpath(os.path.join(root, name), self.root)
                    )
        else:
            for name in sorted(os.listdir(base)):
                if os.path.isfile(os.path.join(base, name)):
                    found.append(os.path.relpath(os.path.join(base, name), self.root))

        return sorted(found)

    def directories(self, directory=""):
        base = self.path(directory)

        if not os.path.isdir(base):
            return []

        return sorted(
            os.path.relpath(os.path.join(base, name), self.root)
            for name in os.listdir(base)
            if os.path.isdir(os.path.join(base, name))
        )

    # -- writing ----------------------------------------------------------

    def put(self, relative, contents):
        path = self.path(relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        mode = "wb" if isinstance(contents, (bytes, bytearray)) else "w"
        kwargs = {} if mode == "wb" else {"encoding": "utf-8"}

        with open(path, mode, **kwargs) as handle:
            handle.write(contents)

        # Private files should not be world-readable on a shared host, where
        # other accounts may sit on the same filesystem.
        if self.visibility == "private":
            try:
                os.chmod(path, 0o600)
            except OSError:
                pass

        return True

    def append(self, relative, contents):
        path = self.path(relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "a", encoding="utf-8") as handle:
            handle.write(contents)

        return True

    def put_file(self, relative, uploaded):
        """Store an UploadedFile from a multipart form."""
        return self.put(relative, uploaded.read())

    def copy(self, source, destination):
        target = self.path(destination)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(self.path(source), target)

        return True

    def move(self, source, destination):
        target = self.path(destination)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.move(self.path(source), target)

        return True

    def delete(self, *relatives):
        deleted = 0

        for relative in relatives:
            try:
                os.remove(self.path(relative))
                deleted += 1
            except (OSError, ValueError):
                continue

        return deleted

    def make_directory(self, relative):
        os.makedirs(self.path(relative), exist_ok=True)

        return True

    def delete_directory(self, relative):
        try:
            shutil.rmtree(self.path(relative))

            return True
        except (OSError, ValueError):
            return False


class FilesystemManager:
    def __init__(self, config=None, base_path=""):
        self.config = dict(config or {})
        self.base_path = base_path
        self._disks = {}

    def disk(self, name=None):
        name = name or self.config.get("default", "local")

        if name not in self._disks:
            self._disks[name] = self._build(name)

        return self._disks[name]

    def _build(self, name):
        settings = (self.config.get("disks", {}) or {}).get(name)

        if settings is None:
            raise ValueError(
                "Disk [{}] is not configured. Add it to config/filesystems.py.".format(name)
            )

        root = settings.get("root", "storage/app")

        if not os.path.isabs(root):
            root = os.path.join(self.base_path, root)

        return LocalDisk(root, settings.get("url"), settings.get("visibility", "private"))

    # The default disk's methods, so Storage.put(...) works without .disk().
    def __getattr__(self, name):
        return getattr(self.disk(), name)
