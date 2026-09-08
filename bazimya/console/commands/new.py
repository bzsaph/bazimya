"""bazimya new — scaffold an application."""

import os
import secrets
import shutil
import stat

from ..command import Command

#: Skeleton files are stored with a .stub suffix so that packaging tools do
#: not try to import or byte-compile a template that contains placeholders.
STUB_SUFFIX = ".stub"

#: Never copied into a new project, and never worth shipping.
IGNORED_FILES = {".DS_Store", "Thumbs.db", "desktop.ini", ".directory"}

IGNORED_DIRECTORIES = {"__pycache__", ".DS_Store"}


class NewCommand(Command):
    name = "new"

    description = "Create a new Bazimya application"

    usage = "bazimya new <name> [--force]"

    needs_application = False

    def handle(self):
        raw = self.argument(0)

        if not raw:
            self.error("  Please give the application a name.")
            self.line("")
            self.line("      " + self.usage)
            self.line("")

            return 1

        target = raw if os.path.isabs(raw) else os.path.join(os.getcwd(), raw)
        target = os.path.normpath(target)
        app_name = os.path.basename(target)

        if os.path.isdir(target) and os.listdir(target) and not self.flag("force"):
            self.error("  Directory [{}] already exists and is not empty.".format(app_name))
            self.line("  Use --force to write into it anyway.")

            return 1

        skeleton = self.framework_path("stubs", "app")

        if not os.path.isdir(skeleton):
            self.error("  The application skeleton is missing at " + skeleton)

            return 1

        self.line("")
        self.info("  Creating a Bazimya application in {}".format(app_name))
        self.line("")

        replacements = {
            "name": app_name,
            "slug": self._slug(app_name),
            "key": secrets.token_hex(16),
        }

        count = self._copy(skeleton, target, replacements)

        self._finalise(target, replacements)

        self.success("  Scaffolded {} files.".format(count))
        self._next_steps(app_name)

        return 0

    # -- copying ----------------------------------------------------------

    def _copy(self, source, destination, replacements):
        count = 0

        for root, directories, files in os.walk(source):
            directories[:] = [d for d in directories if d not in IGNORED_DIRECTORIES]

            relative = os.path.relpath(root, source)
            target_directory = (
                destination if relative == "." else os.path.join(destination, relative)
            )

            os.makedirs(target_directory, exist_ok=True)

            for name in files:
                # Editor and OS droppings must never become part of someone's
                # new project, even if one is sitting in the packaged stubs.
                if name.endswith(".pyc") or name in IGNORED_FILES:
                    continue

                target_name = name[: -len(STUB_SUFFIX)] if name.endswith(STUB_SUFFIX) else name
                target_path = os.path.join(target_directory, target_name)

                self._copy_file(os.path.join(root, name), target_path, replacements)
                count += 1

        return count

    def _copy_file(self, source, destination, replacements):
        # .gitkeep and binary-ish files are copied as-is; everything else has
        # its placeholders filled in.
        if os.path.basename(destination) == ".gitkeep":
            shutil.copyfile(source, destination)

            return

        try:
            with open(source, "r", encoding="utf-8") as handle:
                contents = handle.read()
        except UnicodeDecodeError:
            shutil.copyfile(source, destination)

            return

        for key, value in replacements.items():
            contents = contents.replace("{{" + key + "}}", str(value))

        with open(destination, "w", encoding="utf-8") as handle:
            handle.write(contents)

    # -- finishing --------------------------------------------------------

    def _finalise(self, target, replacements):
        # .env is not in the skeleton (it must never be committed); it is
        # written from .env.example with a fresh key.
        example = os.path.join(target, ".env.example")
        environment = os.path.join(target, ".env")

        if os.path.isfile(example) and not os.path.isfile(environment):
            shutil.copyfile(example, environment)

        # Blank the key in the example so the real one is not shared.
        if os.path.isfile(example):
            with open(example, "r", encoding="utf-8") as handle:
                contents = handle.read()

            contents = contents.replace("APP_KEY={}".format(replacements["key"]), "APP_KEY=")

            with open(example, "w", encoding="utf-8") as handle:
                handle.write(contents)

        for executable in ("bazimya", os.path.join("public", "index.py")):
            path = os.path.join(target, executable)

            if os.path.isfile(path):
                mode = os.stat(path).st_mode
                os.chmod(path, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Created here rather than shipped as .gitkeep placeholders: a new
        # project should not open with a dozen empty files in it. Everything
        # here is gitignored anyway, and the framework recreates what it needs
        # on demand — this just means `bazimya doctor` has something to check
        # on the first run.
        for directory in (
            "storage/app/public",
            "storage/framework/views",
            "storage/framework/cache",
            "storage/framework/sessions",
            "storage/framework/testing",
            "storage/logs",
            "bootstrap/cache",
            "database",
            "extensions",
        ):
            os.makedirs(os.path.join(target, directory), exist_ok=True)

    def _next_steps(self, app_name):
        self.line("")
        self.comment("  Next:")
        self.line("")
        self.line("      cd {}".format(app_name))
        self.line("      bazimya migrate")
        self.line("      bazimya serve")
        self.line("")
        self.comment("  Then open http://127.0.0.1:8000")
        self.line("")
        self.comment("  Deploying:")
        self.line("      bazimya build            # VPS (gunicorn + nginx)")
        self.line("      bazimya build --shared   # shared hosting (cPanel)")
        self.line("")

    @staticmethod
    def _slug(value):
        from ...support.strings import slug

        return slug(value)
