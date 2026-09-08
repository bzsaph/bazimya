"""Choosing the language the framework speaks."""

import os
import re

from ...support.lang import DEFAULT, SUPPORTED, locale, translate
from ..command import Command

NAMES = {
    "en": "English",
    "rw": "Ikinyarwanda",
}


class LangCommand(Command):
    name = "lang"

    description = "Show or change the language Bazimya speaks"

    usage = "bazimya lang [en|rw]"

    # Someone who has not made a project yet still needs to be able to switch.
    needs_application = False

    def handle(self):
        wanted = self.argument(0)

        if wanted is None:
            return self._show()

        wanted = wanted.strip().lower()

        if wanted not in SUPPORTED:
            self.error("  Unsupported language: {}".format(wanted))
            self.line("")
            self.line("  Available:")

            for tag in SUPPORTED:
                self.line("      {}   {}".format(tag, NAMES.get(tag, tag)))

            self.line("")

            return 1

        return self._set(wanted)

    def _show(self):
        current = locale()

        self.line("")
        self.line("  " + translate("Language") + ": {}  ({})".format(
            current, NAMES.get(current, current)
        ))
        self.line("")

        for tag in SUPPORTED:
            marker = "*" if tag == current else " "
            self.line("    {} {}   {}".format(marker, tag, NAMES.get(tag, tag)))

        self.line("")
        self.comment("  Change it with:  bazimya lang rw")
        self.line("")

        return 0

    def _set(self, tag):
        if self.app is None:
            # No project to write to, so tell them the one thing that works
            # everywhere rather than silently doing nothing.
            self.line("")
            self.warn("  Not inside a project, so there is no .env to change.")
            self.line("")
            self.line("  Use it for a single command:")
            self.line("")
            self.line("      BAZIMYA_LANG={} bazimya new my-app".format(tag))
            self.line("")

            return 1

        path = os.path.join(self.app.base_path, ".env")

        if not os.path.isfile(path):
            self.error("  No .env file at " + self.relative(path))

            return 1

        with open(path, "r", encoding="utf-8") as handle:
            contents = handle.read()

        line = "APP_LOCALE={}".format(tag)

        if re.search(r"(?m)^\s*APP_LOCALE\s*=.*$", contents):
            contents = re.sub(r"(?m)^\s*APP_LOCALE\s*=.*$", line, contents)
        else:
            contents = contents.rstrip("\n") + "\n" + line + "\n"

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(contents)

        # Say it in the language they just chose, which is the clearest possible
        # confirmation that it worked.
        from ...support import lang as lang_module

        lang_module.set_locale(tag)

        self.line("")
        self.success("  Language set to {} ({}).".format(tag, NAMES.get(tag, tag)))
        self.line("")

        if tag != DEFAULT:
            self.comment(translate(
                "  Everything Bazimya says will now be in {}.", NAMES.get(tag, tag)
            ))
            self.line("")

        return 0
