"""Compiles a .baz.html template into Python source.

The syntax is Blade's, so a template reads the same as the Laravel one it was
ported from:

    @extends('layouts.app')

    @section('content')
        <h1>{{ title }}</h1>

        @forelse post in posts
            <article>{{ post['title'] }}</article>
        @empty
            <p>Nothing here yet.</p>
        @endforelse
    @endsection

Everything between the directives is Python, not PHP — `{{ post['title'] }}`,
`@if len(posts) > 2`, `@foreach post in posts`.

Compilation produces one function that appends to a buffer:

    def __bazimya_template__():
        __append('<h1>')
        __append(__e(title))
        ...

which is then executed with the view data as its globals, so `title` and
`posts` resolve as plain names.
"""

import re

#: Directives whose argument is an expression running to the end of the line
#: when it is not wrapped in parentheses.
EXPRESSION_DIRECTIVES = {
    "if",
    "elseif",
    "elif",
    "unless",
    "while",
    "for",
    "foreach",
    "forelse",
}

#: Directives that close a block.
CLOSING = {
    "endif",
    "endunless",
    "endwhile",
    "endfor",
    "endforeach",
    "endforelse",
    "endsection",
    "endpython",
    "endisset",
    "endempty",
    "endverbatim",
}

_LOOP_TARGET = re.compile(r"^\s*(?P<target>.+?)\s+in\s+(?P<iterable>.+?)\s*$", re.DOTALL)
_AS_TARGET = re.compile(r"^\s*(?P<iterable>.+?)\s+as\s+(?P<target>.+?)\s*$", re.DOTALL)


class TemplateSyntaxError(Exception):
    def __init__(self, message, template=None, line=None):
        self.template = template
        self.line = line

        location = ""
        if template:
            location = " in {}".format(template)
        if line:
            location += " on line {}".format(line)

        super().__init__(message + location)


class Compiler:
    INDENT = "    "

    def __init__(self, template_name=None):
        self.template_name = template_name
        self._lines = []
        self._indent = 1
        self._blocks = []
        self._counter = 0

    # -- entry point ------------------------------------------------------

    def compile(self, source):
        self._lines = []
        self._indent = 1
        self._blocks = []
        self._counter = 0

        self._emit("def __bazimya_template__():", indent=0)

        self._walk(source)

        if self._blocks:
            unclosed = self._blocks[-1]
            raise TemplateSyntaxError(
                "@{} was never closed (expected @{})".format(
                    unclosed["directive"], unclosed["closes"]
                ),
                self.template_name,
                unclosed["line"],
            )

        self._emit("pass")

        return "\n".join(self._lines) + "\n"

    # -- scanning ---------------------------------------------------------

    def _walk(self, source):
        position = 0
        length = len(source)
        buffer = []
        line = 1

        while position < length:
            character = source[position]

            # Comments: {{-- ... --}}
            if source.startswith("{{--", position):
                end = source.find("--}}", position)

                if end == -1:
                    raise TemplateSyntaxError("Unclosed {{-- comment", self.template_name, line)

                line += source.count("\n", position, end)
                position = end + 4
                continue

            # Literal escapes: @{{ ... }} and @@directive
            if source.startswith("@{{", position):
                buffer.append("{{")
                position += 3
                continue

            if source.startswith("@@", position):
                buffer.append("@")
                position += 2
                continue

            # Raw output: {!! ... !!}
            if source.startswith("{!!", position):
                end = source.find("!!}", position)

                if end == -1:
                    raise TemplateSyntaxError("Unclosed {!! !!}", self.template_name, line)

                expression = source[position + 3 : end].strip()
                self._flush(buffer)
                self._emit_expression(expression, escaped=False, line=line)
                line += source.count("\n", position, end)
                position = end + 3
                continue

            # Escaped output: {{ ... }}
            if source.startswith("{{", position):
                end = source.find("}}", position)

                if end == -1:
                    raise TemplateSyntaxError("Unclosed {{ }}", self.template_name, line)

                expression = source[position + 2 : end].strip()
                self._flush(buffer)
                self._emit_expression(expression, escaped=True, line=line)
                line += source.count("\n", position, end)
                position = end + 2
                continue

            # Directives: @name, @name(...), @name expression
            if character == "@":
                match = re.match(r"@([A-Za-z_][A-Za-z0-9_]*)", source[position:])

                if match:
                    name = match.group(1)

                    # @python and @verbatim take their bodies literally, so
                    # they are scanned out here rather than compiled.
                    if name in ("python", "verbatim"):
                        self._flush(buffer)
                        position, line = self._raw_block(source, position + match.end(), name, line)

                        continue

                    after = position + match.end()
                    arguments, after, consumed_lines = self._read_arguments(source, after, name)

                    self._flush(buffer)
                    self._handle(name, arguments, line)

                    line += consumed_lines
                    position = after

                    # A directive alone on its line should not leave a blank
                    # line behind in the output.
                    if position < length and source[position] == "\n" and self._is_block_directive(name):
                        position += 1
                        line += 1

                    continue

            if character == "\n":
                line += 1

            buffer.append(character)
            position += 1

        self._flush(buffer)

    def _raw_block(self, source, position, name, line):
        """Consume @python…@endpython or @verbatim…@endverbatim verbatim.

        Neither body is template source: one is Python to run, the other is
        text to print untouched — so both are taken out of the scanner's hands
        entirely rather than being compiled and then undone.
        """
        closing = "@end" + name
        end = source.find(closing, position)

        if end == -1:
            raise TemplateSyntaxError(
                "@{} was never closed (expected {})".format(name, closing),
                self.template_name,
                line,
            )

        body = source[position:end]
        consumed = body.count("\n")

        # Drop the newline that follows the opening directive.
        if body.startswith("\n"):
            body = body[1:]

        if name == "verbatim":
            if body:
                self._emit("__append({!r})".format(body))
        else:
            statements = _dedent(body).strip("\n")

            if statements.strip():
                for statement in statements.splitlines():
                    self._emit(statement if statement.strip() else "")

        position = end + len(closing)

        # Swallow the newline after @endpython / @endverbatim too.
        if position < len(source) and source[position] == "\n":
            position += 1
            consumed += 1

        return position, line + consumed

    def _read_arguments(self, source, position, name):
        """Return (arguments, new_position, lines_consumed)."""
        start = position

        while position < len(source) and source[position] in " \t":
            position += 1

        if position < len(source) and source[position] == "(":
            end = self._matching_paren(source, position)

            if end == -1:
                raise TemplateSyntaxError(
                    "Unbalanced parentheses after @{}".format(name), self.template_name
                )

            arguments = source[position + 1 : end]

            return arguments.strip(), end + 1, arguments.count("\n")

        if name in EXPRESSION_DIRECTIVES:
            end = source.find("\n", position)
            end = len(source) if end == -1 else end
            arguments = source[position:end].strip()

            if not arguments:
                raise TemplateSyntaxError(
                    "@{} needs a condition".format(name), self.template_name
                )

            return arguments, end, 0

        return None, start, 0

    @staticmethod
    def _matching_paren(source, position):
        """Find the ')' closing the '(' at `position`, ignoring quoted text."""
        depth = 0
        quote = None
        index = position

        while index < len(source):
            character = source[index]

            if quote:
                if character == "\\":
                    index += 2
                    continue

                if character == quote:
                    quote = None
            elif character in ("'", '"'):
                quote = character
            elif character == "(":
                depth += 1
            elif character == ")":
                depth -= 1

                if depth == 0:
                    return index

            index += 1

        return -1

    @staticmethod
    def _is_block_directive(name):
        return name in CLOSING or name in {
            "if",
            "elseif",
            "elif",
            "else",
            "unless",
            "while",
            "for",
            "foreach",
            "forelse",
            "empty",
            "section",
            "extends",
            "python",
            "isset",
            "break",
            "continue",
            "verbatim",
        }

    # -- emitting ---------------------------------------------------------

    def _emit(self, code, indent=None):
        level = self._indent if indent is None else indent
        self._lines.append(self.INDENT * level + code)

    def _flush(self, buffer):
        if not buffer:
            return

        text = "".join(buffer)
        buffer.clear()

        if text:
            self._emit("__append({!r})".format(text))

    def _emit_expression(self, expression, escaped, line):
        if not expression:
            return

        self._check_php(expression, line)

        self._emit(
            "__append(__e({}))".format(expression)
            if escaped
            else "__append(__raw({}))".format(expression)
        )

    def _check_php(self, expression, line):
        """Catch the most common porting mistake with a message that says so."""
        if re.search(r"\$[A-Za-z_]", expression):
            raise TemplateSyntaxError(
                "'{}' looks like PHP. Bazimya templates are Python: write "
                "{{{{ title }}}}, not {{{{ $title }}}}".format(expression),
                self.template_name,
                line,
            )

        if "->" in expression:
            raise TemplateSyntaxError(
                "'{}' uses PHP's -> operator. Use a dot for attributes "
                "(post.title) or brackets for dict keys (post['title'])".format(expression),
                self.template_name,
                line,
            )

    def _unique(self, prefix):
        self._counter += 1

        return "__{}_{}".format(prefix, self._counter)

    def _open(self, directive, closes, line, indent=True, **extra):
        """Open a block.

        `indent` is False for directives that pair up in the template but emit
        no Python block — @section captures at runtime, so indenting its body
        would produce an IndentationError in the generated function.
        """
        block = {"directive": directive, "closes": closes, "line": line, "indent": indent}
        block.update(extra)
        self._blocks.append(block)

        if indent:
            self._indent += 1

        return block

    def _close(self, directive, line, expected):
        if not self._blocks:
            raise TemplateSyntaxError(
                "@{} has no matching @{}".format(directive, expected),
                self.template_name,
                line,
            )

        block = self._blocks[-1]

        if block["closes"] != directive:
            raise TemplateSyntaxError(
                "@{} closes @{}, but @{} is still open".format(
                    directive, expected, block["directive"]
                ),
                self.template_name,
                line,
            )

        if block.get("indent", True):
            self._indent -= 1

        return self._blocks.pop()

    # -- directives -------------------------------------------------------

    def _handle(self, name, arguments, line):
        handler = getattr(self, "_directive_" + name, None)

        if handler is None:
            raise TemplateSyntaxError(
                "Unknown directive @{}".format(name), self.template_name, line
            )

        handler(arguments, line)

    # Inheritance ---------------------------------------------------------

    def _directive_extends(self, arguments, line):
        if not arguments:
            raise TemplateSyntaxError("@extends needs a template name", self.template_name, line)

        self._emit("__view.extend({})".format(arguments))

    def _directive_section(self, arguments, line):
        if not arguments:
            raise TemplateSyntaxError("@section needs a name", self.template_name, line)

        # @section('title', 'Home') is the one-liner form; no @endsection.
        parts = _split_arguments(arguments)

        if len(parts) > 1:
            self._emit("__view.set_section({}, {})".format(parts[0], parts[1]))

            return

        self._emit("__view.start_section({})".format(arguments))
        self._open("section", "endsection", line, indent=False)

    def _directive_endsection(self, arguments, line):
        self._close("endsection", line, "section")
        self._emit("__view.stop_section()")

    def _directive_show(self, arguments, line):
        """@show ends a section and immediately prints it, as Blade does."""
        self._close("endsection", line, "section")
        self._emit("__append(__view.stop_section(render=True))")

    def _directive_parent(self, arguments, line):
        self._emit("__append(__view.parent_section())")

    def _directive_yield(self, arguments, line):
        if not arguments:
            raise TemplateSyntaxError("@yield needs a section name", self.template_name, line)

        self._emit("__append(__view.yield_section({}))".format(arguments))

    def _directive_include(self, arguments, line):
        if not arguments:
            raise TemplateSyntaxError("@include needs a template name", self.template_name, line)

        parts = _split_arguments(arguments)
        extra = parts[1] if len(parts) > 1 else "None"

        self._emit("__append(__view.include({}, __ctx, {}))".format(parts[0], extra))

    def _directive_includeIf(self, arguments, line):
        parts = _split_arguments(arguments)
        extra = parts[1] if len(parts) > 1 else "None"

        self._emit(
            "__append(__view.include({}, __ctx, {}, missing_ok=True))".format(parts[0], extra)
        )

    def _directive_each(self, arguments, line):
        """@each('view', items, 'name') — render one template per item."""
        parts = _split_arguments(arguments)

        if len(parts) < 3:
            raise TemplateSyntaxError(
                "@each needs a template, an iterable and a variable name",
                self.template_name,
                line,
            )

        self._emit(
            "__append(__view.each({}, {}, {}, __ctx))".format(parts[0], parts[1], parts[2])
        )

    # Conditionals --------------------------------------------------------

    def _directive_if(self, arguments, line):
        self._emit("if {}:".format(arguments))
        self._open("if", "endif", line)

    def _directive_elseif(self, arguments, line):
        self._indent -= 1
        self._emit("elif {}:".format(arguments))
        self._indent += 1

    _directive_elif = _directive_elseif

    def _directive_else(self, arguments, line):
        if not self._blocks:
            raise TemplateSyntaxError("@else has no matching @if", self.template_name, line)

        self._indent -= 1
        self._emit("else:")
        self._indent += 1

    def _directive_endif(self, arguments, line):
        self._close("endif", line, "if")

    def _directive_unless(self, arguments, line):
        self._emit("if not ({}):".format(arguments))
        self._open("unless", "endunless", line)

    def _directive_endunless(self, arguments, line):
        self._close("endunless", line, "unless")

    def _directive_isset(self, arguments, line):
        self._emit("if __view.is_set(__ctx, {!r}):".format(arguments.strip()))
        self._open("isset", "endisset", line)

    def _directive_endisset(self, arguments, line):
        self._close("endisset", line, "isset")

    # Loops ---------------------------------------------------------------

    def _directive_foreach(self, arguments, line):
        target, iterable = _loop_parts(arguments, "foreach", self.template_name, line)
        self._emit("for {} in {}:".format(target, iterable))
        self._open("foreach", "endforeach", line)

    def _directive_endforeach(self, arguments, line):
        self._close("endforeach", line, "foreach")

    def _directive_for(self, arguments, line):
        target, iterable = _loop_parts(arguments, "for", self.template_name, line)
        self._emit("for {} in {}:".format(target, iterable))
        self._open("for", "endfor", line)

    def _directive_endfor(self, arguments, line):
        self._close("endfor", line, "for")

    def _directive_while(self, arguments, line):
        self._emit("while {}:".format(arguments))
        self._open("while", "endwhile", line)

    def _directive_endwhile(self, arguments, line):
        self._close("endwhile", line, "while")

    def _directive_forelse(self, arguments, line):
        target, iterable = _loop_parts(arguments, "forelse", self.template_name, line)
        variable = self._unique("forelse")

        # Materialise the iterable: it has to be tested for emptiness *and*
        # iterated, which a generator would not survive.
        self._emit("{} = list({})".format(variable, iterable))
        self._emit("if {}:".format(variable))
        self._indent += 1
        self._emit("for {} in {}:".format(target, variable))

        self._blocks.append(
            {"directive": "forelse", "closes": "endforelse", "line": line, "in_empty": False}
        )
        self._indent += 1

    def _directive_empty(self, arguments, line):
        # @empty means two different things: the else-branch of @forelse, or
        # a standalone "is this falsy" block.
        if self._blocks and self._blocks[-1]["directive"] == "forelse":
            block = self._blocks[-1]

            if block["in_empty"]:
                raise TemplateSyntaxError(
                    "@forelse already has an @empty", self.template_name, line
                )

            block["in_empty"] = True
            self._indent -= 2
            self._emit("else:")
            self._indent += 1

            return

        if arguments is None:
            raise TemplateSyntaxError(
                "@empty needs a value, or must follow @forelse", self.template_name, line
            )

        self._emit("if not ({}):".format(arguments))
        self._open("empty", "endempty", line)

    def _directive_endempty(self, arguments, line):
        self._close("endempty", line, "empty")

    def _directive_endforelse(self, arguments, line):
        block = self._blocks[-1] if self._blocks else None

        if block is None or block["directive"] != "forelse":
            raise TemplateSyntaxError(
                "@endforelse has no matching @forelse", self.template_name, line
            )

        self._blocks.pop()

        # Without @empty we are two levels deep (if + for); with it, one.
        self._indent -= 1 if block["in_empty"] else 2

    def _directive_break(self, arguments, line):
        self._emit("break" if not arguments else "if {}: break".format(arguments))

    def _directive_continue(self, arguments, line):
        self._emit("continue" if not arguments else "if {}: continue".format(arguments))

    # Helpers -------------------------------------------------------------

    def _directive_csrf(self, arguments, line):
        self._emit("__append(__view.csrf_field())")

    def _directive_method(self, arguments, line):
        if not arguments:
            raise TemplateSyntaxError("@method needs a verb, e.g. @method('PUT')", self.template_name, line)

        self._emit("__append(__view.method_field({}))".format(arguments))

    def _directive_json(self, arguments, line):
        self._emit("__append(__view.to_json({}))".format(arguments))

    def _directive_dump(self, arguments, line):
        self._emit("__append(__view.dump({}))".format(arguments))

    def _directive_route(self, arguments, line):
        self._emit("__append(__e(__view.route({})))".format(arguments))

    def _directive_asset(self, arguments, line):
        self._emit("__append(__e(__view.asset({})))".format(arguments))

    def _directive_config(self, arguments, line):
        self._emit("__append(__e(__view.config({})))".format(arguments))


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------


def _loop_parts(arguments, directive, template, line):
    """Accept both `item in items` and Blade's `items as item`."""
    if not arguments:
        raise TemplateSyntaxError(
            "@{} needs something to loop over".format(directive), template, line
        )

    match = _LOOP_TARGET.match(arguments)

    if match:
        return match.group("target").strip(), match.group("iterable").strip()

    match = _AS_TARGET.match(arguments)

    if match:
        return match.group("target").strip(), match.group("iterable").strip()

    raise TemplateSyntaxError(
        "@{} should read '@{} item in items' — got '{}'".format(directive, directive, arguments),
        template,
        line,
    )


def _split_arguments(arguments):
    """Split a directive's arguments on top-level commas only."""
    parts = []
    depth = 0
    quote = None
    current = []

    for character in arguments:
        if quote:
            current.append(character)

            if character == quote:
                quote = None

            continue

        if character in ("'", '"'):
            quote = character
        elif character in "([{":
            depth += 1
        elif character in ")]}":
            depth -= 1
        elif character == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue

        current.append(character)

    if current:
        parts.append("".join(current).strip())

    return [part for part in parts if part]


def _dedent(source):
    """Strip the common leading whitespace from a @python block."""
    lines = source.splitlines()
    indents = [len(line) - len(line.lstrip()) for line in lines if line.strip()]

    if not indents:
        return source

    common = min(indents)

    return "\n".join(line[common:] if line.strip() else "" for line in lines)
