"""A single registered route.

URIs use braced placeholders:

    /posts/{id}
    /posts/{slug?}          optional — also matches /posts
    /files/{path}           one segment
"""

import re

from ..support.aliases import AliasMixin

_PLACEHOLDER = re.compile(r"^\{([A-Za-z_][A-Za-z0-9_]*)(\?)?\}$")


class Route(AliasMixin):
    def __init__(self, methods, uri, action):
        self.methods = list(methods)
        self.uri = self._normalise(uri)
        self.action = action
        self.route_name = None
        self.name_prefix = ""
        self.middlewares = []
        self.excluded_middlewares = []
        self.constraints = {}
        self.defaults = {}
        self._pattern = None
        self._parameters = {}

    @staticmethod
    def _normalise(uri):
        uri = "/" + str(uri).strip("/")

        return "/" if uri == "/" else uri.rstrip("/")

    # -- fluent configuration ---------------------------------------------

    def name(self, name):
        # A name prefix set by an enclosing group is applied here rather than
        # at registration, because .name() is chained after the route exists.
        self.route_name = self.name_prefix + name

        return self

    def middleware(self, *middleware):
        for item in middleware:
            if isinstance(item, (list, tuple, set)):
                self.middlewares.extend(item)
            else:
                self.middlewares.append(item)

        return self

    def without_middleware(self, *middleware):
        for item in middleware:
            if isinstance(item, (list, tuple, set)):
                self.excluded_middlewares.extend(item)
            else:
                self.excluded_middlewares.append(item)

        return self

    def where(self, parameter=None, expression=None, **constraints):
        """Constrain a placeholder with a regular expression.

            Route.get('/posts/{id}', ...).where('id', r'\\d+')
            Route.get('/posts/{id}', ...).where(id=r'\\d+')
        """
        if parameter is not None and expression is not None:
            self.constraints[parameter] = expression

        self.constraints.update(constraints)
        self._pattern = None

        return self

    def where_number(self, *parameters):
        return self.where(**{name: r"[0-9]+" for name in parameters})

    def where_alpha(self, *parameters):
        return self.where(**{name: r"[A-Za-z]+" for name in parameters})

    def where_slug(self, *parameters):
        return self.where(**{name: r"[A-Za-z0-9\-_]+" for name in parameters})

    def defaults_to(self, **values):
        self.defaults.update(values)

        return self

    # -- matching ---------------------------------------------------------

    def pattern(self):
        """Compile the URI into a regex, one segment at a time.

        Segment-by-segment rather than escaping the whole URI and then undoing
        the escapes around placeholders — that second approach is where
        routers usually pick up their matching bugs.
        """
        if self._pattern is not None:
            return self._pattern

        if self.uri == "/":
            self._pattern = re.compile(r"^/$")

            return self._pattern

        source = ""

        for segment in self.uri.strip("/").split("/"):
            match = _PLACEHOLDER.match(segment)

            if match:
                name, optional = match.group(1), match.group(2) == "?"
                expression = self.constraints.get(name, r"[^/]+")

                if optional:
                    # The optional parameter swallows the slash before it, so
                    # /posts/{slug?} matches both /posts and /posts/hello.
                    source += r"(?:/(?P<{}>{}))?".format(name, expression)
                else:
                    source += r"/(?P<{}>{})".format(name, expression)

                continue

            source += "/" + re.escape(segment)

        self._pattern = re.compile("^" + (source or "/") + "$")

        return self._pattern

    def matches(self, path):
        match = self.pattern().match(path)

        if not match:
            return False

        parameters = dict(self.defaults)
        parameters.update({k: v for k, v in match.groupdict().items() if v is not None})
        self._parameters = parameters

        return True

    def parameters(self):
        return dict(self._parameters)

    def parameter_names(self):
        return [
            match.group(1)
            for match in (_PLACEHOLDER.match(s) for s in self.uri.strip("/").split("/"))
            if match
        ]

    def accepts(self, method):
        return method.upper() in self.methods

    # -- URL generation ---------------------------------------------------

    def url(self, **parameters):
        """Build this route's URL, filling in its placeholders."""
        if self.uri == "/":
            return "/"

        built = []

        for segment in self.uri.strip("/").split("/"):
            match = _PLACEHOLDER.match(segment)

            if not match:
                built.append(segment)
                continue

            name, optional = match.group(1), match.group(2) == "?"

            if name in parameters:
                built.append(str(parameters.pop(name)))
            elif optional:
                continue
            else:
                raise ValueError(
                    "Route [{}] needs a value for {{{}}}.".format(
                        self.route_name or self.uri, name
                    )
                )

        url = "/" + "/".join(built)

        # Anything left over becomes a query string, which is what you want
        # when generating a link with filters on it.
        if parameters:
            from urllib.parse import urlencode

            url += "?" + urlencode(parameters)

        return url

    def gather_middleware(self):
        excluded = set(self.excluded_middlewares)

        return [m for m in self.middlewares if m not in excluded]

    def __repr__(self):
        return "<Route {} {}>".format("|".join(self.methods), self.uri)
