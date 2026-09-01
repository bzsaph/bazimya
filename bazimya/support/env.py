"""Reading .env.

Values are coerced on the way out, because a config file that
says `debug = Env.get("APP_DEBUG", False)` should get a real boolean, not the
string "false" — which is truthy, and is the single most common way a debug
flag ends up on in production.
"""

import os
import re

_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*)$")
_INTERPOLATION = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

_TRUE = {"true", "(true)", "yes", "on", "1"}
_FALSE = {"false", "(false)", "no", "off", "0"}
_NULL = {"null", "(null)", "none", ""}


class Env:
    """The parsed .env, layered under the real process environment."""

    _values = {}
    _loaded_from = None

    @classmethod
    def load(cls, path, override=False):
        """Read a .env file. Real environment variables win unless `override`."""
        cls._loaded_from = path

        if not os.path.isfile(path):
            return cls

        with open(path, "r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()

                if not stripped or stripped.startswith("#"):
                    continue

                match = _LINE.match(line)

                if not match:
                    continue

                key, raw = match.group(1), match.group(2).strip()
                value = cls._unquote(raw)

                # ${OTHER} refers to something already defined.
                value = _INTERPOLATION.sub(
                    lambda m: str(cls._values.get(m.group(1), os.environ.get(m.group(1), ""))),
                    value,
                )

                if override or key not in os.environ:
                    cls._values[key] = value

        return cls

    @staticmethod
    def _unquote(raw):
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
            body = raw[1:-1]

            # Only double quotes give escape sequences their usual meaning.
            if raw[0] == '"':
                body = body.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')

            return body

        # An unquoted value ends at the first inline comment.
        hash_index = raw.find(" #")

        return (raw[:hash_index] if hash_index != -1 else raw).strip()

    @classmethod
    def get(cls, key, default=None):
        """Fetch a value, coerced to bool/None/int where that is unambiguous."""
        if key in os.environ:
            raw = os.environ[key]
        elif key in cls._values:
            raw = cls._values[key]
        else:
            return default

        return cls._coerce(raw, default)

    @staticmethod
    def _coerce(raw, default=None):
        lowered = raw.strip().lower()

        if lowered in _TRUE:
            return True

        if lowered in _FALSE:
            # "0" as a port or a count should stay 0, not become False. Only
            # coerce to a bool when the default says this is a flag.
            if lowered in ("0", "1") and not isinstance(default, bool):
                return int(lowered)

            return False

        if lowered in _NULL:
            return None if default is None else default

        if isinstance(default, int) and not isinstance(default, bool):
            try:
                return int(raw)
            except ValueError:
                return raw

        return raw

    @classmethod
    def all(cls):
        merged = dict(cls._values)
        merged.update(os.environ)

        return merged

    @classmethod
    def has(cls, key):
        return key in os.environ or key in cls._values

    @classmethod
    def path(cls):
        return cls._loaded_from

    @classmethod
    def reset(cls):
        cls._values = {}
        cls._loaded_from = None


def env(key, default=None):
    """Module-level helper, so config files read as plain assignments."""
    return Env.get(key, default)
