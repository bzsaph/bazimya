"""Laravel's method names, on top of Python's.

Bazimya's own methods are snake_case, because that is what Python code looks
like. But the point of this framework is that Laravel code should port across
almost unchanged, and Laravel's methods are camelCase:

    User.where('active', 1).orderBy('name').firstOrFail()     # Laravel's spelling
    User.where('active', 1).order_by('name').first_or_fail()  # the same call

So every camelCase name falls through to its snake_case twin. Nothing is
duplicated: there is one implementation, and one alias path to it.

The lookup only ever runs when normal attribute access has already failed, so
it costs nothing on the common path.
"""

import re

_BOUNDARY = re.compile(r"(?<!^)(?=[A-Z])")


def camel_to_snake(name):
    """orderBy -> order_by, whereIn -> where_in, toSql -> to_sql"""
    return _BOUNDARY.sub("_", name).lower()


def looks_camel(name):
    """True for orderBy, False for order_by, __init__ or ORDER."""
    return (
        not name.startswith("_")
        and not name.islower()
        and not name.isupper()
        and any(character.isupper() for character in name)
    )


class AliasMixin:
    """Give an instance Laravel's camelCase spellings."""

    def __getattr__(self, name):
        if looks_camel(name):
            snake = camel_to_snake(name)

            if snake != name:
                try:
                    return object.__getattribute__(self, snake)
                except AttributeError:
                    pass

        raise AttributeError(
            "{!r} object has no attribute {!r}".format(type(self).__name__, name)
        )


class AliasMeta(type):
    """Give a *class* Laravel's camelCase spellings.

    Needed for the static-style calls that are the whole reason this exists:
    `User.orderBy(...)` is a lookup on the class, not on an instance.
    """

    def __getattr__(cls, name):
        if looks_camel(name):
            snake = camel_to_snake(name)

            if snake != name:
                for klass in cls.__mro__:
                    if snake in klass.__dict__:
                        return getattr(cls, snake)

        raise AttributeError(
            "type object {!r} has no attribute {!r}".format(cls.__name__, name)
        )
