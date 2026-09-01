"""View components.

Laravel's `<x-alert type="error">…</x-alert>`, in two halves:

  - a template at resources/views/components/alert.baz.html
  - optionally a class at app/View/Components/Alert.py, which prepares data
    before the template renders

Anonymous components — a template with no class — work on their own, which is
what most components are.

    <x-alert type="error">Something went wrong.</x-alert>

becomes a render of `components.alert` with `type='error'` and `slot` set to
the inner content.
"""

import importlib
import re

#: <x-name attr="value" :bound="expression"> … </x-name>, or self-closing.
OPENING = re.compile(
    r"<x-(?P<name>[A-Za-z0-9_.\-]+)(?P<attributes>(?:\s+[^<>]*?)?)(?P<close>/?)>",
    re.DOTALL,
)

ATTRIBUTE = re.compile(
    r"""(?P<bound>:?)(?P<name>[A-Za-z_@][A-Za-z0-9_.\-]*)"""
    r"""(?:\s*=\s*(?P<quote>["'])(?P<value>.*?)(?P=quote))?""",
    re.DOTALL,
)


class Component:
    """Base class for a component with logic behind it.

    Attributes passed in the tag arrive as constructor arguments; whatever
    `data()` returns is what the template sees.

        class Alert(Component):
            def __init__(self, type='info', dismissible=False):
                self.type = type
                self.dismissible = dismissible

            def classes(self):
                return 'alert alert-' + self.type
    """

    #: Override to render a template other than components.<snake name>.
    template = None

    def data(self):
        """Everything public on the instance, plus its methods."""
        values = {k: v for k, v in vars(self).items() if not k.startswith("_")}

        for name in dir(type(self)):
            if name.startswith("_") or name in values:
                continue

            attribute = getattr(self, name, None)

            if callable(attribute) and name not in ("data", "render", "template"):
                values[name] = attribute

        return values

    def render(self):
        return self.template


def resolve_component_class(name):
    """Find app/View/Components/<Studly>.py for a component name, if it exists.

    Anonymous components are the common case, so a missing class is not an
    error — it just means the template stands alone.
    """
    from ..support.strings import studly

    class_name = studly(name.replace(".", "_").replace("-", "_"))

    try:
        module = importlib.import_module("app.View.Components." + class_name)
    except ImportError:
        return None

    return getattr(module, class_name, None)


def component_template(name):
    """`alert` -> `components.alert`; `forms.input` -> `components.forms.input`.

    Hyphens are kept: <x-input-error> looks for components/input-error, the
    same filename Laravel uses. Only the backing class name is studly-cased.
    """
    return "components." + name


def parse_attributes(source):
    """Turn a tag's attributes into (static, bound) dicts.

    `type="error"` is a literal; `:count="len(items)"` is a Python expression
    evaluated in the template's scope — the same split Blade makes.
    """
    static = {}
    bound = {}

    for match in ATTRIBUTE.finditer(source or ""):
        name = match.group("name")
        value = match.group("value")
        key = name.replace("-", "_").replace(".", "_")

        if match.group("bound"):
            bound[key] = value if value is not None else "None"
        elif value is None:
            # A bare attribute is a flag: <x-alert dismissible>
            static[key] = True
        else:
            static[key] = value

    return static, bound


def find_closing(source, name, start):
    """Locate the matching </x-name>, allowing the same component to nest."""
    opening = "<x-{}".format(name)
    closing = "</x-{}>".format(name)

    depth = 1
    index = start

    while index < len(source):
        next_open = source.find(opening, index)
        next_close = source.find(closing, index)

        if next_close == -1:
            return -1

        if next_open != -1 and next_open < next_close:
            # Only count it as nesting if it is really a tag, not a prefix
            # (<x-alert> vs <x-alert-heading>).
            after = source[next_open + len(opening) : next_open + len(opening) + 1]

            if after in (" ", ">", "/", "\t", "\n"):
                depth += 1

            index = next_open + len(opening)
            continue

        depth -= 1

        if depth == 0:
            return next_close

        index = next_close + len(closing)

    return -1
