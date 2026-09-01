"""Locating, compiling and rendering .baz.html templates.

Templates live in resources/views. Compiled Python is written to
storage/framework/views and reused until the template changes, so the cost of
compiling is paid once rather than per request.
"""

import html
import json as jsonlib
import os
import re
from hashlib import md5

from ..support.aliases import AliasMixin
from .compiler import Compiler, TemplateSyntaxError

EXTENSION = ".baz.html"

#: How deep @extends / @include may nest before we call it a loop.
MAX_DEPTH = 32


class ViewNotFound(Exception):
    pass


class Markup(str):
    """A string that is already safe HTML; {{ }} will not escape it again."""

    def __html__(self):
        return str(self)


class View(AliasMixin):
    def __init__(self, view_path, cache_path, debug=False, root=None):
        self.view_path = str(view_path).rstrip("/")
        self.cache_path = str(cache_path).rstrip("/")
        self.debug = debug

        # Cache keys are derived from the template's path *relative to here*.
        # Absolute paths would key the cache to the machine that built it, so
        # a bundle compiled locally and uploaded would miss on every template
        # and recompile — which fails outright when storage/ is read-only.
        self.root = os.path.abspath(root) if root else None

        self._namespaces = {}
        self._shared = {}
        self._sections = {}
        self._section_stack = []
        self._buffers = []
        self._parents = []
        self._codes = {}
        self._csrf_token = None

    # -- configuration ----------------------------------------------------

    def share(self, key, value=None):
        """Data available to every template."""
        if isinstance(key, dict):
            self._shared.update(key)
        else:
            self._shared[key] = value

        return self

    def add_namespace(self, namespace, directory):
        """Serve a package's templates under a prefix, e.g. blog::index."""
        namespace = str(namespace).lower()
        self._namespaces.setdefault(namespace, [])

        if directory not in self._namespaces[namespace]:
            self._namespaces[namespace].append(directory)

        return self

    def namespaces(self):
        return dict(self._namespaces)

    def set_csrf_token(self, token):
        self._csrf_token = token

        return self

    # -- locating ---------------------------------------------------------

    def resolve(self, template):
        """'posts.index' -> resources/views/posts/index.baz.html"""
        if "::" in template:
            return self._resolve_namespaced(template)

        return os.path.join(self.view_path, template.replace(".", os.sep) + EXTENSION)

    def _resolve_namespaced(self, template):
        namespace, _, name = template.partition("::")
        namespace = namespace.lower()
        relative = name.replace(".", os.sep) + EXTENSION

        # An override in the application always beats what the package ships.
        override = os.path.join(self.view_path, "vendor", namespace, relative)

        if os.path.isfile(override):
            return override

        for directory in self._namespaces.get(namespace, []):
            candidate = os.path.join(directory, relative)

            if os.path.isfile(candidate):
                return candidate

        registered = self._namespaces.get(namespace)

        # Name a real directory in the error rather than an empty path.
        return os.path.join(registered[0], relative) if registered else override

    def exists(self, template):
        return os.path.isfile(self.resolve(template))

    # -- rendering --------------------------------------------------------

    def render(self, template, data=None, **kwargs):
        payload = dict(data or {})
        payload.update(kwargs)

        # A top-level render starts with a clean slate; nested ones (a layout,
        # an include) deliberately keep the sections captured so far.
        if not self._buffers:
            self._sections = {}

        return self._render(template, payload, depth=0)

    def _render(self, template, data, depth):
        if depth > MAX_DEPTH:
            raise RecursionError(
                "Template [{}] is {} levels deep — check for an @extends or "
                "@include loop.".format(template, depth)
            )

        path = self.resolve(template)

        if not os.path.isfile(path):
            raise ViewNotFound(
                "View [{}] was not found at {}".format(template, path)
            )

        code = self._code(path, template)

        context = dict(self._shared)
        context.update(data)

        namespace = dict(context)
        namespace.update(
            {
                "__view": self,
                "__ctx": context,
                "__e": self.escape,
                "__raw": self.raw,
                "__append": self.append,
            }
        )

        self._buffers.append([])
        self._parents.append(None)

        try:
            exec(code, namespace)  # noqa: S102 — the code is our own compiler's output
            namespace["__bazimya_template__"]()
        finally:
            content = "".join(self._buffers.pop())
            parent = self._parents.pop()

        if parent:
            # The child's sections are still recorded, which is exactly what
            # the layout's @yield calls need.
            return self._render(parent, data, depth + 1)

        return content

    # -- compilation ------------------------------------------------------

    def _code(self, path, template):
        cache_file = self._cache_file(path)
        mtime = os.path.getmtime(path)

        cached = self._codes.get(path)

        if cached and cached[0] >= mtime:
            return cached[1]

        source = None

        if os.path.isfile(cache_file) and os.path.getmtime(cache_file) >= mtime:
            with open(cache_file, "r", encoding="utf-8") as handle:
                source = handle.read()
        else:
            source = self._compile(path, template)
            self._write_cache(cache_file, source)

        try:
            code = compile(source, cache_file, "exec")
        except SyntaxError as error:
            # A syntax error here is almost always an expression inside {{ }}
            # or an @if, so point at the template rather than the generated
            # file the author never sees.
            raise TemplateSyntaxError(
                "{} (compiled line {})".format(error.msg, error.lineno),
                template,
            ) from error

        self._codes[path] = (mtime, code)

        return code

    def _compile(self, path, template):
        with open(path, "r", encoding="utf-8") as handle:
            return Compiler(template).compile(handle.read())

    def cache_key(self, path):
        path = os.path.abspath(path)

        if self.root:
            try:
                relative = os.path.relpath(path, self.root)
            except ValueError:
                relative = path
            else:
                # Only use it when the template really is inside the project;
                # ../../ up out of the root is no more portable than absolute.
                if not relative.startswith(os.pardir):
                    path = relative.replace(os.sep, "/")

        return md5(path.encode("utf-8")).hexdigest()

    def _cache_file(self, path):
        return os.path.join(self.cache_path, self.cache_key(path) + ".py")

    def _write_cache(self, cache_file, source):
        try:
            os.makedirs(self.cache_path, exist_ok=True)

            # Write then rename, so a concurrent request never reads a
            # half-written file.
            temporary = "{}.{}.tmp".format(cache_file, os.getpid())

            with open(temporary, "w", encoding="utf-8") as handle:
                handle.write(source)

            os.replace(temporary, cache_file)
        except OSError:
            # A read-only storage/ should not stop the page rendering; it just
            # means recompiling every time.
            pass

    def clear_cache(self):
        if not os.path.isdir(self.cache_path):
            return 0

        cleared = 0

        for entry in os.listdir(self.cache_path):
            if entry.endswith(".py") or entry.endswith(".tmp"):
                try:
                    os.remove(os.path.join(self.cache_path, entry))
                    cleared += 1
                except OSError:
                    pass

        self._codes = {}

        return cleared

    # -- runtime, called from compiled templates --------------------------

    def append(self, text):
        if self._buffers:
            self._buffers[-1].append(text)

    def escape(self, value):
        if value is None:
            return ""

        if isinstance(value, Markup) or hasattr(value, "__html__"):
            return value.__html__() if hasattr(value, "__html__") else str(value)

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, (dict, list, tuple)):
            return html.escape(jsonlib.dumps(value, default=str), quote=True)

        return html.escape(str(value), quote=True)

    def raw(self, value):
        return "" if value is None else str(value)

    def is_set(self, context, name):
        value = context.get(name.strip(), None)

        return value is not None

    # Inheritance ---------------------------------------------------------

    def extend(self, layout):
        if self._parents:
            self._parents[-1] = layout

    def start_section(self, name):
        self._section_stack.append(name)
        self._buffers.append([])

    def stop_section(self, render=False):
        if not self._section_stack:
            raise TemplateSyntaxError("@endsection without a matching @section")

        name = self._section_stack.pop()
        content = "".join(self._buffers.pop())

        # A child's section wins over the layout's default, which is what
        # @section in a layout followed by @show is for.
        if name not in self._sections:
            self._sections[name] = content

        return self._sections[name] if render else ""

    def set_section(self, name, content):
        if name not in self._sections:
            self._sections[name] = self.escape(content)

    def yield_section(self, name, default=""):
        return self._sections.get(name, default)

    def parent_section(self):
        name = self._section_stack[-1] if self._section_stack else None

        return self._sections.get(name, "") if name else ""

    def sections(self):
        return dict(self._sections)

    # Composition ---------------------------------------------------------

    def include(self, template, context=None, extra=None, missing_ok=False):
        if missing_ok and not self.exists(template):
            return ""

        data = dict(context or {})
        data.update(extra or {})

        return self._render(template, data, depth=len(self._buffers))

    def each(self, template, items, variable, context=None, empty_template=None):
        rendered = []

        for item in items or []:
            data = dict(context or {})
            data[variable] = item
            rendered.append(self._render(template, data, depth=len(self._buffers)))

        if not rendered and empty_template:
            return self._render(empty_template, dict(context or {}), depth=len(self._buffers))

        return "".join(rendered)

    # Helpers -------------------------------------------------------------

    def csrf_field(self):
        token = self._csrf_token or ""

        return '<input type="hidden" name="_token" value="{}">'.format(html.escape(token, True))

    def csrf_token(self):
        return self._csrf_token or ""

    def method_field(self, verb):
        return '<input type="hidden" name="_method" value="{}">'.format(
            html.escape(str(verb).upper(), True)
        )

    def to_json(self, value):
        """Safe to drop inside a <script> block."""
        encoded = jsonlib.dumps(value, default=str)

        # </script> inside a JSON string would end the block early.
        return encoded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")

    def dump(self, value):
        import pprint

        return '<pre style="background:#111;color:#eee;padding:1rem;overflow:auto">{}</pre>'.format(
            html.escape(pprint.pformat(value), True)
        )

    def route(self, name, **parameters):
        from ..facades import Route

        return Route.url(name, **parameters)

    def asset(self, path):
        return "/" + str(path).lstrip("/")

    def config(self, key, default=None):
        from ..facades import Config

        return Config.get(key, default)


def markup(value):
    """Mark a string as already-safe HTML."""
    return Markup(value)
