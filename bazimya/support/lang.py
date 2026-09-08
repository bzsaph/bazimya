"""Translating what the framework says.

Bazimya speaks English by default and Kinyarwanda when asked. The catalogue is
keyed by the English sentence itself, so a sentence nobody has translated yet
falls back to readable English instead of a bare key like "new.scaffolded" —
a half-translated CLI stays usable, which matters more here than tidiness.

Resolution order, first hit wins:

    1. BAZIMYA_LANG          — explicit, per command
    2. APP_LOCALE in .env    — per project
    3. LC_ALL / LANG         — whatever the machine is already set to
    4. English

Indentation carries meaning in CLI output, so lookups ignore the whitespace
around a sentence and put it back afterwards. The catalogue holds sentences,
not layout.
"""

import os
import re

DEFAULT = "en"

#: Languages with a catalogue in bazimya/lang/.
SUPPORTED = ("en", "rw")

_catalogues = {}
_locale = None


def _normalise(tag):
    """"rw_RW.UTF-8", "RW", "kin" -> "rw". None when nothing usable."""
    if not tag:
        return None

    tag = str(tag).strip().lower()

    for separator in (".", "@"):
        tag = tag.split(separator)[0]

    tag = tag.replace("-", "_").split("_")[0]

    # ISO 639-3 for Kinyarwanda, which some systems report instead of "rw".
    if tag == "kin":
        tag = "rw"

    return tag if tag in SUPPORTED else None


def _detect():
    from .env import Env

    explicit = _normalise(os.environ.get("BAZIMYA_LANG"))

    if explicit:
        return explicit

    try:
        configured = _normalise(Env.get("APP_LOCALE"))
    except Exception:  # noqa: BLE001 — a broken .env must not break output
        configured = None

    if configured:
        return configured

    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        detected = _normalise(os.environ.get(variable))

        if detected:
            return detected

    return DEFAULT


def locale():
    global _locale

    if _locale is None:
        _locale = _detect()

    return _locale


def set_locale(tag):
    """Force a language. Falls back to English for anything unsupported."""
    global _locale

    _locale = _normalise(tag) or DEFAULT

    return _locale


def reset():
    """Forget the detected language, so the next call looks again."""
    global _locale

    _locale = None


def catalogue(tag=None):
    tag = tag or locale()

    if tag in _catalogues:
        return _catalogues[tag]

    messages = {}

    if tag != DEFAULT:
        try:
            module = __import__("bazimya.lang." + tag, fromlist=["MESSAGES"])
            messages = getattr(module, "MESSAGES", {})
        except Exception:  # noqa: BLE001 — a missing catalogue is just English
            messages = {}

    _catalogues[tag] = messages

    return messages


# -- matching sentences that already have their values filled in ----------
#
# Output reaches us as "Scaffolded 99 files.", not as the template it was
# built from, because .format() ran at the call site. Rather than rewrite
# every call site, each catalogue key containing {} becomes a regex, and the
# captured values are poured into the translation. Longest literal text wins,
# so a specific sentence beats a vague one.

_PLACEHOLDER = re.compile(r"\{[^{}]*\}")
_patterns_cache = {}


def _patterns(tag):
    if tag in _patterns_cache:
        return _patterns_cache[tag]

    compiled = []

    for source, target in catalogue(tag).items():
        if not _PLACEHOLDER.search(source):
            continue

        literal = _PLACEHOLDER.sub("", source)

        # A key that is nothing but placeholders would match every line.
        if len(literal.strip()) < 3:
            continue

        pieces = [re.escape(piece) for piece in _PLACEHOLDER.split(source)]
        compiled.append((len(literal), re.compile("^" + "(.*?)".join(pieces) + "$", re.S), target))

    compiled.sort(key=lambda item: item[0], reverse=True)
    _patterns_cache[tag] = compiled

    return compiled


def _match(text, tag):
    for _, pattern, target in _patterns(tag):
        found = pattern.match(text)

        if found is None:
            continue

        try:
            return target.format(*found.groups())
        except (IndexError, KeyError, ValueError):
            return target

    return None


def translate(text, *args, **kwargs):
    """Translate a sentence, then fill in its {} placeholders.

    Formatting happens after the lookup so that translations can move the
    placeholders around — Kinyarwanda does not put them where English does.
    A translation with the wrong number of placeholders falls back to English
    rather than raising: an error message is the worst possible place to
    raise a second error.
    """
    if not isinstance(text, str) or not text.strip():
        return text

    stripped = text.strip()
    leading = text[: len(text) - len(text.lstrip())]
    trailing = text[len(text.rstrip()) :]

    tag = locale()
    known = catalogue(tag)

    if stripped in known:
        translated = known[stripped]
    elif not args and not kwargs:
        # Already rendered by the caller — recover the sentence behind it.
        translated = _match(stripped, tag) or stripped
    else:
        translated = stripped

    if args or kwargs:
        try:
            translated = translated.format(*args, **kwargs)
        except (IndexError, KeyError, ValueError):
            try:
                translated = stripped.format(*args, **kwargs)
            except (IndexError, KeyError, ValueError):
                translated = stripped

    return leading + translated + trailing


#: The short name every caller uses.
t = translate
