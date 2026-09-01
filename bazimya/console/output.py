"""Terminal output.

Colour is used when the stream is a TTY and NO_COLOR is unset, and dropped
otherwise — piping `bazimya route:list` into grep should not produce escape
codes.
"""

import os
import shutil
import sys


class Output:
    COLORS = {
        "reset": "\033[0m",
        "bold": "\033[1m",
        "dim": "\033[2m",
        "red": "\033[31m",
        "green": "\033[32m",
        "yellow": "\033[33m",
        "blue": "\033[34m",
        "magenta": "\033[35m",
        "cyan": "\033[36m",
        "grey": "\033[90m",
    }

    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self.colored = self._supports_color()

    def _supports_color(self):
        if os.environ.get("NO_COLOR"):
            return False

        if os.environ.get("FORCE_COLOR"):
            return True

        return hasattr(self.stream, "isatty") and self.stream.isatty()

    def paint(self, message, color):
        if not self.colored or color not in self.COLORS:
            return message

        return "{}{}{}".format(self.COLORS[color], message, self.COLORS["reset"])

    # -- writing ----------------------------------------------------------

    def write(self, message=""):
        self.stream.write(message)
        self.stream.flush()

    def line(self, message=""):
        self.write(message + "\n")

    def info(self, message):
        self.line(self.paint(message, "cyan"))

    def success(self, message):
        self.line(self.paint(message, "green"))

    def warn(self, message):
        self.line(self.paint(message, "yellow"))

    def error(self, message):
        sys.stderr.write(self.paint(message, "red") + "\n")
        sys.stderr.flush()

    def comment(self, message):
        self.line(self.paint(message, "grey"))

    def bold(self, message):
        return self.paint(message, "bold")

    # -- structures -------------------------------------------------------

    def table(self, headers, rows, indent="  "):
        if not rows:
            return

        columns = len(headers)
        widths = [len(str(h)) for h in headers]

        for row in rows:
            for index in range(columns):
                cell = str(row[index]) if index < len(row) else ""
                widths[index] = max(widths[index], len(cell))

        # Keep the table inside the terminal by trimming the widest column
        # rather than letting rows wrap into unreadable soup.
        available = shutil.get_terminal_size((100, 24)).columns - len(indent)
        overflow = sum(widths) + 2 * (columns - 1) - available

        if overflow > 0:
            widest = widths.index(max(widths))
            widths[widest] = max(8, widths[widest] - overflow)

        def render(cells, painter=None):
            parts = []

            for index in range(columns):
                cell = str(cells[index]) if index < len(cells) else ""

                if len(cell) > widths[index]:
                    cell = cell[: widths[index] - 1] + "…"

                text = cell.ljust(widths[index])
                parts.append(painter(text) if painter else text)

            return indent + "  ".join(parts).rstrip()

        self.line(render(headers, lambda t: self.paint(t, "bold")))
        self.line(indent + self.paint("  ".join("─" * w for w in widths), "grey"))

        for row in rows:
            self.line(render(row))

    def bullet(self, message):
        self.line("  " + self.paint("·", "grey") + " " + message)

    def confirm(self, question, default=False):
        suffix = "[Y/n]" if default else "[y/N]"
        self.write("{} {} ".format(question, suffix))

        try:
            answer = input().strip().lower()
        except EOFError:
            return default

        if not answer:
            return default

        return answer in ("y", "yes")

    def ask(self, question, default=None):
        hint = " [{}]".format(default) if default is not None else ""
        self.write("{}{} ".format(question, hint))

        try:
            answer = input().strip()
        except EOFError:
            return default

        return answer or default
