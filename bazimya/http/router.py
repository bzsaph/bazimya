"""The router: registration, matching, the middleware pipeline, dispatch.

Written to read like routes/web.php does in Laravel:

    Route.get('/', [HomeController, 'index']).name('home')
    Route.post('/posts', [PostController, 'store'])
    Route.get('/posts/{id}', [PostController, 'show']).where_number('id')

    Route.middleware('auth').prefix('admin').group(lambda: [
        Route.get('/dashboard', [AdminController, 'index']).name('admin.dashboard'),
    ])
"""

import inspect

from ..support.aliases import AliasMixin
from .exceptions import HttpException, MethodNotAllowed, NotFound
from .request import Request
from .response import Response
from .route import Route

HTTP_VERBS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


class Router(AliasMixin):
    def __init__(self, container=None):
        self.container = container
        self._routes = []
        self._group_stack = []
        self._aliases = {}
        self._global_middleware = []
        self._groups = {}

    # -- verbs ------------------------------------------------------------

    def get(self, uri, action):
        return self.add_route(["GET", "HEAD"], uri, action)

    def post(self, uri, action):
        return self.add_route(["POST"], uri, action)

    def put(self, uri, action):
        return self.add_route(["PUT"], uri, action)

    def patch(self, uri, action):
        return self.add_route(["PATCH"], uri, action)

    def delete(self, uri, action):
        return self.add_route(["DELETE"], uri, action)

    def options(self, uri, action):
        return self.add_route(["OPTIONS"], uri, action)

    def any(self, uri, action):
        return self.add_route(list(HTTP_VERBS), uri, action)

    def match(self, methods, uri, action):
        if isinstance(methods, str):
            methods = [methods]

        methods = [m.upper() for m in methods]

        if "GET" in methods and "HEAD" not in methods:
            methods.append("HEAD")

        return self.add_route(methods, uri, action)

    def view(self, uri, template, data=None):
        """A route that only renders a template — Laravel's Route::view."""
        payload = dict(data or {})

        def handler(request):
            from ..facades import View

            return Response.html(View.render(template, payload))

        return self.get(uri, handler)

    def redirect(self, uri, destination, status=302):
        return self.any(uri, lambda request: Response.redirect(destination, status))

    # -- registration -----------------------------------------------------

    def add_route(self, methods, uri, action):
        prefix = ""
        middleware = []
        name_prefix = ""

        for group in self._group_stack:
            if group["prefix"]:
                prefix += "/" + group["prefix"]

            middleware.extend(group["middleware"])
            name_prefix += group["name"]

        route = Route(methods, prefix + "/" + str(uri).strip("/"), action)

        if middleware:
            route.middleware(middleware)

        route.name_prefix = name_prefix
        self._routes.append(route)

        return route

    def group(self, attributes=None, callback=None, **kwargs):
        """Share a prefix, middleware stack or name prefix across routes.

            Route.group({'prefix': 'admin', 'middleware': ['auth']}, lambda: [
                Route.get('/users', [UserController, 'index']),
            ])
        """
        if callable(attributes) and callback is None:
            attributes, callback = {}, attributes

        attributes = dict(attributes or {})
        attributes.update(kwargs)

        self._group_stack.append(
            {
                "prefix": str(attributes.get("prefix", "") or "").strip("/"),
                "middleware": _as_list(attributes.get("middleware")),
                "name": attributes.get("name", "") or "",
            }
        )

        try:
            if callback is not None:
                callback()
        finally:
            self._group_stack.pop()

        return self

    # Laravel's fluent group builders: Route.middleware('auth').group(...)

    def middleware(self, *middleware):
        return _GroupBuilder(self, {"middleware": _flatten(middleware)})

    def prefix(self, prefix):
        return _GroupBuilder(self, {"prefix": prefix})

    def name(self, name):
        return _GroupBuilder(self, {"name": name})

    # -- resource routes --------------------------------------------------

    def resource(self, uri, controller, only=None, exclude=None, parameter=None):
        """The seven RESTful routes, with Laravel's names and verbs."""
        from ..support.strings import singular, snake

        base = str(uri).strip("/")
        parameter = parameter or snake(singular(base.split("/")[-1]))

        blueprint = [
            ("index", ["GET", "HEAD"], "/" + base),
            ("create", ["GET", "HEAD"], "/" + base + "/create"),
            ("store", ["POST"], "/" + base),
            ("show", ["GET", "HEAD"], "/{}/{{{}}}".format(base, parameter)),
            ("edit", ["GET", "HEAD"], "/{}/{{{}}}/edit".format(base, parameter)),
            ("update", ["PUT", "PATCH"], "/{}/{{{}}}".format(base, parameter)),
            ("destroy", ["DELETE"], "/{}/{{{}}}".format(base, parameter)),
        ]

        wanted = set(only) if only else {action for action, _, _ in blueprint}
        wanted -= set(exclude or [])

        created = []

        for action, methods, route_uri in blueprint:
            if action not in wanted:
                continue

            # Registering a route the controller cannot serve would turn a
            # missing method into a 500 on the first request instead of a 404.
            if not _controller_has(controller, action):
                continue

            created.append(
                self.add_route(methods, route_uri, [controller, action]).name(
                    "{}.{}".format(base.replace("/", "."), action)
                )
            )

        return created

    def api_resource(self, uri, controller, **kwargs):
        kwargs.setdefault("exclude", [])
        kwargs["exclude"] = list(kwargs["exclude"]) + ["create", "edit"]

        return self.resource(uri, controller, **kwargs)

    # -- middleware aliases -----------------------------------------------

    def alias_middleware(self, alias, middleware):
        """Give a middleware class a short name, as app/Http/Kernel does."""
        self._aliases[alias] = middleware

        return self

    def middleware_group(self, name, middleware):
        self._groups[name] = _as_list(middleware)

        return self

    def push_middleware(self, middleware):
        """Middleware that runs on every request."""
        self._global_middleware.extend(_as_list(middleware))

        return self

    def aliases(self):
        return dict(self._aliases)

    def has_middleware_group(self, name):
        return name in self._groups

    def middleware_groups(self):
        return dict(self._groups)

    # -- introspection ----------------------------------------------------

    def routes(self):
        return list(self._routes)

    def named(self, name):
        for route in self._routes:
            if route.route_name == name:
                return route

        return None

    def url(self, name, **parameters):
        """Generate a URL from a route name, like Laravel's route() helper."""
        route = self.named(name)

        if route is None:
            raise LookupError("There is no route named [{}].".format(name))

        return route.url(**parameters)

    def has(self, name):
        return self.named(name) is not None

    # -- dispatch ---------------------------------------------------------

    def dispatch(self, request):
        method = request.method()
        path = request.path()
        path_matched = False

        for route in self._routes:
            if not route.matches(path):
                continue

            path_matched = True

            if not route.accepts(method):
                continue

            request.set_route_parameters(route.parameters())

            return self.run_route(route, request)

        # A path that matched with the wrong verb is a 405, not a 404 — the
        # difference tells a client whether to retry differently.
        if path_matched:
            raise MethodNotAllowed(
                "The {} method is not supported for {}.".format(method, path)
            )

        raise NotFound("No route matches {} {}.".format(method, path))

    def global_middleware(self):
        """Middleware that runs on every request, 404s included.

        Applied by Application around the whole dispatch rather than here, so
        that a request which matches no route still passes through it — a
        security header is no use only on the pages that happened to exist.
        """
        return list(self._global_middleware)

    def wrap_middleware(self, middleware, next_handler):
        return self._wrap(middleware, next_handler)

    def run_route(self, route, request):
        stack = self._expand(route.gather_middleware())

        def destination(req):
            return Response.make(self.call_action(route.action, req, route.parameters()))

        pipeline = destination

        for middleware in reversed(stack):
            pipeline = self._wrap(middleware, pipeline)

        return Response.make(pipeline(request))

    def _expand(self, middleware):
        """Flatten middleware groups into the individual middleware."""
        expanded = []

        for item in middleware:
            if isinstance(item, str) and item in self._groups:
                expanded.extend(self._groups[item])
            else:
                expanded.append(item)

        return expanded

    def _wrap(self, middleware, next_handler):
        resolved = self._aliases.get(middleware, middleware) if isinstance(middleware, str) else middleware

        if isinstance(resolved, str):
            raise LookupError(
                "Middleware [{}] was not found. Register it in app/Http/Kernel.py "
                "or pass the class itself.".format(resolved)
            )

        def handler(request):
            instance = resolved() if inspect.isclass(resolved) else resolved

            target = getattr(instance, "handle", instance)

            return target(request, next_handler)

        return handler

    def call_action(self, action, request, parameters):
        """Supported shapes: a callable, [Controller, 'method'], 'Controller@method'."""
        if isinstance(action, str) and "@" in action:
            raise TypeError(
                "String actions like '{}' need a controller to resolve against. "
                "Pass [Controller, 'method'] instead.".format(action)
            )

        if isinstance(action, (list, tuple)) and len(action) == 2:
            target, method_name = action
            instance = target() if inspect.isclass(target) else target
            handler = getattr(instance, method_name, None)

            if handler is None:
                raise AttributeError(
                    "Method [{}] was not found on [{}].".format(
                        method_name, getattr(target, "__name__", target)
                    )
                )
        elif callable(action):
            handler = action
        else:
            raise TypeError("The route action is not callable: {!r}".format(action))

        return self._invoke(handler, request, parameters)

    @staticmethod
    def _invoke(handler, request, parameters):
        """Pass route parameters the way the handler asks for them.

        Handlers written as `def show(self, request, id)` get them positionally
        by name; one written as `def show(self, request)` gets none, rather
        than a TypeError about an unexpected argument.
        """
        try:
            signature = inspect.signature(handler)
        except (TypeError, ValueError):
            return handler(request, **parameters)

        accepted = {}
        takes_kwargs = False

        for name, parameter in signature.parameters.items():
            if parameter.kind is inspect.Parameter.VAR_KEYWORD:
                takes_kwargs = True
            elif name in parameters:
                accepted[name] = parameters[name]

        if takes_kwargs:
            accepted = dict(parameters)

        return handler(request, **accepted)


class _GroupBuilder:
    """Supports Route.middleware('auth').prefix('admin').group(...)."""

    def __init__(self, router, attributes):
        self._router = router
        self._attributes = dict(attributes)

    def middleware(self, *middleware):
        existing = _as_list(self._attributes.get("middleware"))
        self._attributes["middleware"] = existing + _flatten(middleware)

        return self

    def prefix(self, prefix):
        self._attributes["prefix"] = prefix

        return self

    def name(self, name):
        self._attributes["name"] = name

        return self

    def group(self, callback):
        return self._router.group(self._attributes, callback)


def _as_list(value):
    if value is None:
        return []

    if isinstance(value, (list, tuple, set)):
        return list(value)

    return [value]


def _flatten(values):
    flat = []

    for value in values:
        flat.extend(_as_list(value))

    return flat


def _controller_has(controller, method):
    if isinstance(controller, str):
        return True

    return callable(getattr(controller, method, None))
