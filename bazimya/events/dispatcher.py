"""Events.

The Event facade. Listeners are registered in app/Providers/
EventServiceProvider.py and fired from anywhere:

    Event.listen(UserRegistered, SendWelcomeEmail)
    Event.dispatch(UserRegistered(user))

Dispatch is synchronous — there is no queue, so a slow listener slows the
request that fired it.
"""

import inspect


class Dispatcher:
    def __init__(self):
        self._listeners = {}
        self._wildcards = []

    # -- registering ------------------------------------------------------

    def listen(self, event, listener=None):
        """Register a listener. Usable as a decorator:

            @Event.listen(UserRegistered)
            def send_welcome(event): ...
        """
        if listener is None:
            def decorator(handler):
                self.listen(event, handler)

                return handler

            return decorator

        key = self._key(event)

        if key == "*":
            self._wildcards.append(listener)
        else:
            self._listeners.setdefault(key, []).append(listener)

        return self

    def subscribe(self, subscriber):
        """Let a class register its own listeners, via subscribe(dispatcher)."""
        instance = subscriber() if inspect.isclass(subscriber) else subscriber
        instance.subscribe(self)

        return self

    def forget(self, event):
        self._listeners.pop(self._key(event), None)

        return self

    def flush(self):
        self._listeners = {}
        self._wildcards = []

        return self

    # -- firing -----------------------------------------------------------

    def dispatch(self, event, payload=None):
        """Fire an event and return what the listeners returned.

        A listener returning False stops the ones after it, which is how you
        cancel an action from a listener.
        """
        key = self._key(event)
        results = []

        for listener in list(self._listeners.get(key, [])) + list(self._wildcards):
            result = self._call(listener, event, payload)

            if result is False:
                break

            results.append(result)

        return results

    def until(self, event, payload=None):
        """Fire until a listener returns something that is not None."""
        key = self._key(event)

        for listener in list(self._listeners.get(key, [])) + list(self._wildcards):
            result = self._call(listener, event, payload)

            if result is not None:
                return result

        return None

    def has_listeners(self, event):
        return bool(self._listeners.get(self._key(event))) or bool(self._wildcards)

    def listeners(self, event):
        return list(self._listeners.get(self._key(event), []))

    # -- internals --------------------------------------------------------

    @staticmethod
    def _key(event):
        if isinstance(event, str):
            return event

        if inspect.isclass(event):
            return event.__name__

        return type(event).__name__

    @staticmethod
    def _call(listener, event, payload):
        # A class listener is instantiated and its handle() called; a plain
        # function is called directly.
        if inspect.isclass(listener):
            instance = listener()
            handler = getattr(instance, "handle", instance)
        else:
            handler = listener

        try:
            signature = inspect.signature(handler)
            count = len(
                [
                    p
                    for p in signature.parameters.values()
                    if p.kind
                    in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                ]
            )
        except (TypeError, ValueError):
            count = 1

        if count == 0:
            return handler()

        if count >= 2 and payload is not None:
            return handler(event, payload)

        return handler(event)
