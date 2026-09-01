"""Small string helpers, used by the generators and the router."""

import re
import unicodedata

_CAMEL_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")
_NON_WORD = re.compile(r"[^A-Za-z0-9]+")


def studly(value):
    """user_profile -> UserProfile"""
    parts = _NON_WORD.split(str(value))

    return "".join(part[:1].upper() + part[1:] for part in parts if part)


def camel(value):
    """user_profile -> userProfile"""
    result = studly(value)

    return result[:1].lower() + result[1:]


def snake(value):
    """UserProfile -> user_profile"""
    value = _NON_WORD.sub("_", str(value))
    value = _CAMEL_BOUNDARY.sub("_", value)

    return re.sub(r"_+", "_", value).strip("_").lower()


def kebab(value):
    return snake(value).replace("_", "-")


def slug(value, separator="-"):
    value = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode()
    value = re.sub(r"[^A-Za-z0-9]+", separator, value).strip(separator)

    return value.lower() or "item"


def plural(value):
    """Good enough for table names; override with `table` on the model when
    the guess is wrong."""
    value = str(value)

    if not value:
        return value

    lowered = value.lower()

    irregular = {
        "person": "people",
        "man": "men",
        "woman": "women",
        "child": "children",
        "tooth": "teeth",
        "foot": "feet",
        "mouse": "mice",
        "goose": "geese",
    }

    if lowered in irregular:
        return irregular[lowered]

    if lowered.endswith(("s", "x", "z", "ch", "sh")):
        return value + "es"

    if lowered.endswith("y") and len(value) > 1 and lowered[-2] not in "aeiou":
        return value[:-1] + "ies"

    if lowered.endswith("f"):
        return value[:-1] + "ves"

    if lowered.endswith("fe"):
        return value[:-2] + "ves"

    return value + "s"


def singular(value):
    value = str(value)
    lowered = value.lower()

    irregular = {
        "people": "person",
        "men": "man",
        "women": "woman",
        "children": "child",
        "teeth": "tooth",
        "feet": "foot",
        "mice": "mouse",
        "geese": "goose",
    }

    if lowered in irregular:
        return irregular[lowered]

    if lowered.endswith("ies") and len(value) > 3:
        return value[:-3] + "y"

    if lowered.endswith("ves"):
        return value[:-3] + "f"

    if lowered.endswith("es") and lowered[:-2].endswith(("s", "x", "z", "ch", "sh")):
        return value[:-2]

    if lowered.endswith("s") and not lowered.endswith("ss"):
        return value[:-1]

    return value


def title(value):
    return " ".join(word.capitalize() for word in snake(value).split("_"))
