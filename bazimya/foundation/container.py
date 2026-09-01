"""The service container.

Three verbs: bind, singleton, instance — plus make to get
something back out. Keys are strings ("router", "db") or classes.
"""

import inspect

from ..support.aliases import AliasMixin


class BindingResolutionError(RuntimeError):
    pass


class Container(AliasMixin):
    def __init__(self):
        self._bindings = {}
        self._instances = {}
        self._aliases = {}

    # -- registering ------------------------------------------------------

    def bind(self, key, factory, shared=False):
        """Register a factory. It is called with the container each time."""
        self._bindings[self._key(key)] = {"factory": factory, "shared": shared}
        self._instances.pop(self._key(key), None)

        return self

    def singleton(self, key, factory):
        """Register a factory whose result is remembered after the first call."""
        return self.bind(key, factory, shared=True)

    def instance(self, key, value):
        """Register an object that already exists."""
        self._instances[self._key(key)] = value

        return self

    def alias(self, alias, key):
        self._aliases[alias] = self._key(key)

        return self

    # -- resolving --------------------------------------------------------

    def make(self, key, *args, **kwargs):
        key = self._aliases.get(self._key(key), self._key(key))

        if key in self._instances:
            return self._instances[key]

        binding = self._bindings.get(key)

        if binding is None:
            return self._build_unbound(key, *args, **kwargs)

        resolved = self._call_factory(binding["factory"], *args, **kwargs)

        if binding["shared"]:
            self._instances[key] = resolved

        return resolved

    def _call_factory(self, factory, *args, **kwargs):
        if not callable(factory):
            return factory

        # A factory may take the container, or nothing at all. Supporting both
        # keeps simple bindings free of a parameter they do not use.
        try:
            signature = inspect.signature(factory)
        except (TypeError, ValueError):
            return factory(*args, **kwargs)

        if args or kwargs:
            return factory(*args, **kwargs)

        return factory(self) if len(signature.parameters) >= 1 else factory()

    def _build_unbound(self, key, *args, **kwargs):
        """An unbound class is still constructible; an unbound string is not."""
        if inspect.isclass(key):
            return key(*args, **kwargs)

        raise BindingResolutionError(
            "Nothing is bound to [{}] in the container.".format(key)
        )

    # -- introspection ----------------------------------------------------

    def bound(self, key):
        key = self._aliases.get(self._key(key), self._key(key))

        return key in self._bindings or key in self._instances

    def forget(self, key):
        key = self._key(key)
        self._bindings.pop(key, None)
        self._instances.pop(key, None)

        return self

    def keys(self):
        return sorted(set(list(self._bindings) + list(self._instances)))

    @staticmethod
    def _key(key):
        return key if isinstance(key, str) else key

    # -- dict-ish sugar ---------------------------------------------------

    def __getitem__(self, key):
        return self.make(key)

    def __setitem__(self, key, value):
        self.instance(key, value)

    def __contains__(self, key):
        return self.bound(key)
