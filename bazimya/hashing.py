"""Password hashing.

Laravel's Hash facade, on Python's hashlib. Two algorithms, both in the
standard library so nothing needs installing:

    Hash.make('secret')                  -> 'scrypt$32768$8$1$<salt>$<hash>'
    Hash.check('secret', hashed)         -> True
    Hash.needs_rehash(hashed)            -> True when the cost has changed

scrypt is the default because it is memory-hard, which is what makes a stolen
password table expensive to attack. pbkdf2 is there for hosts whose OpenSSL
build lacks scrypt.
"""

import hashlib
import hmac
import os
import base64


class HashError(RuntimeError):
    pass


def scrypt_available():
    """Not every OpenSSL build exposes scrypt — the macOS system Python is a
    common example. Detected once rather than discovered at the first login."""
    if not hasattr(hashlib, "scrypt"):
        return False

    try:
        hashlib.scrypt(b"x", salt=b"y", n=2, r=1, p=1, dklen=1)

        return True
    except (ValueError, AttributeError):
        return False


SCRYPT_AVAILABLE = scrypt_available()


class Hasher:
    def __init__(self, config=None):
        self.config = dict(config or {})

    # -- driver selection -------------------------------------------------

    def driver(self):
        """The configured driver, degraded to pbkdf2 where scrypt is absent.

        Falling back is better than failing: pbkdf2 with a high iteration
        count is still a sound choice, and a login that errors because of the
        host's OpenSSL build helps nobody.
        """
        driver = str(self.config.get("driver", "scrypt")).lower()

        if driver == "scrypt" and not SCRYPT_AVAILABLE:
            return "pbkdf2"

        return driver

    def _options(self, driver):
        options = self.config.get(driver, {}) or {}

        if driver == "scrypt":
            return {
                "n": int(options.get("n", 32768)),
                "r": int(options.get("r", 8)),
                "p": int(options.get("p", 1)),
            }

        return {"iterations": int(options.get("iterations", 480000))}

    # -- hashing ----------------------------------------------------------

    def make(self, value, driver=None):
        driver = (driver or self.driver()).lower()
        salt = os.urandom(16)

        if driver == "scrypt":
            options = self._options("scrypt")
            digest = self._scrypt(value, salt, **options)

            return "scrypt${n}${r}${p}${salt}${digest}".format(
                salt=_b64(salt), digest=_b64(digest), **options
            )

        if driver == "pbkdf2":
            options = self._options("pbkdf2")
            digest = self._pbkdf2(value, salt, options["iterations"])

            return "pbkdf2${}${}${}".format(
                options["iterations"], _b64(salt), _b64(digest)
            )

        raise HashError("Unknown hash driver [{}]. Use scrypt or pbkdf2.".format(driver))

    def check(self, value, hashed):
        """Verify a password. Always constant-time, and never raises on a
        malformed hash — a corrupt row should fail the login, not the request."""
        if not hashed or not isinstance(hashed, str):
            return False

        try:
            parts = hashed.split("$")
            algorithm = parts[0]

            if algorithm == "scrypt":
                _, n, r, p, salt, digest = parts
                computed = self._scrypt(
                    value, _unb64(salt), n=int(n), r=int(r), p=int(p)
                )

                return hmac.compare_digest(computed, _unb64(digest))

            if algorithm == "pbkdf2":
                _, iterations, salt, digest = parts
                computed = self._pbkdf2(value, _unb64(salt), int(iterations))

                return hmac.compare_digest(computed, _unb64(digest))
        except (ValueError, TypeError, IndexError, MemoryError):
            return False

        return False

    def needs_rehash(self, hashed):
        """True when the stored hash was made with weaker settings than the
        current config — rehash on the next successful login."""
        if not hashed or not isinstance(hashed, str):
            return True

        parts = hashed.split("$")
        algorithm = parts[0]

        if algorithm != self.driver():
            return True

        try:
            if algorithm == "scrypt":
                options = self._options("scrypt")

                return (
                    int(parts[1]) != options["n"]
                    or int(parts[2]) != options["r"]
                    or int(parts[3]) != options["p"]
                )

            if algorithm == "pbkdf2":
                return int(parts[1]) != self._options("pbkdf2")["iterations"]
        except (ValueError, IndexError):
            return True

        return True

    def info(self, hashed):
        parts = str(hashed or "").split("$")

        return {"algorithm": parts[0] if parts else None}

    # -- primitives -------------------------------------------------------

    @staticmethod
    def _scrypt(value, salt, n, r, p):
        try:
            return hashlib.scrypt(
                _bytes(value), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=n * r * 256
            )
        except (ValueError, AttributeError) as error:
            raise HashError(
                "scrypt is not available in this Python's OpenSSL build. "
                "Set hashing.driver to 'pbkdf2' in config/hashing.py."
            ) from error

    @staticmethod
    def _pbkdf2(value, salt, iterations):
        return hashlib.pbkdf2_hmac("sha256", _bytes(value), salt, iterations, dklen=32)


def _bytes(value):
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def _b64(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(text):
    padding = "=" * (-len(text) % 4)

    return base64.urlsafe_b64decode(text + padding)
