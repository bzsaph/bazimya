"""Loading config/*.py into one dotted-key store.

A config file is a Python module that defines a `config` dict:

    # config/app.py
    from bazimya import env

    config = {
        "name": env("APP_NAME", "Bazimya"),
        "debug": env("APP_DEBUG", False),
    }

which becomes `config("app.name")` and `config("app.debug")`.
"""

import importlib.util
import os


class Repository:
    """Dotted-key access over the merged contents of config/."""

    def __init__(self, config_path=None):
        self._items = {}
        self._path = config_path

        if config_path:
            self.load_directory(config_path)

    def load_directory(self, directory):
        if not os.path.isdir(directory):
            return self

        for entry in sorted(os.listdir(directory)):
            if not entry.endswith(".py") or entry.startswith("_"):
                continue

            key = entry[:-3]
            values = self._load_file(os.path.join(directory, entry))

            if isinstance(values, dict):
                self._items[key] = values

        return self

    @staticmethod
    def _load_file(path):
        """Import a config file directly, without it needing to be a package."""
        name = "bazimya_config_" + os.path.basename(path)[:-3]
        spec = importlib.util.spec_from_file_location(name, path)

        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load the config file at {}".format(path))

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        if hasattr(module, "config"):
            return module.config

        raise RuntimeError(
            "The config file {} must define a `config` dict:\n\n"
            "    config = {{\n        \"key\": \"value\",\n    }}".format(path)
        )

    def get(self, key, default=None):
        value = self._items

        for segment in key.split("."):
            if not isinstance(value, dict) or segment not in value:
                return default

            value = value[segment]

        return value

    def set(self, key, value):
        segments = key.split(".")
        target = self._items

        for segment in segments[:-1]:
            if segment not in target or not isinstance(target[segment], dict):
                target[segment] = {}

            target = target[segment]

        target[segments[-1]] = value

        return self

    def has(self, key):
        sentinel = object()

        return self.get(key, sentinel) is not sentinel

    def all(self):
        return dict(self._items)

    def __call__(self, key, default=None):
        return self.get(key, default)

    def __contains__(self, key):
        return self.has(key)
