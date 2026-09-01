"""bazimya build — produce an upload-ready copy of the application."""

import os

from ...deployment.bundler import LAYOUT_SHARED, LAYOUT_VPS, Bundler
from ..command import Command


class BuildCommand(Command):
    name = "build"

    description = "Build an upload-ready copy of the app for a server"

    usage = "bazimya build [--shared] [--target=build] [--zip] [--with-env]"

    def handle(self):
        application = self.application()

        layout = LAYOUT_SHARED if self.flag("shared") else LAYOUT_VPS

        target = str(self.option("target", "build") or "build")

        if not os.path.isabs(target):
            target = application.path(target)

        self.line("")
        self.info(
            "  Building for " + ("shared hosting (cPanel)" if layout == LAYOUT_SHARED else "a VPS")
        )
        self.line("")

        bundler = Bundler(application, target, layout, self.flag("with-env"))
        bundler.build()

        if self.flag("zip"):
            archive = bundler.zip()
            bundler.notes.append("Archived to " + self.relative(archive))

        self._report(bundler)

        return 0

    def _report(self, bundler):
        self.success("  Build complete — {} files.".format(bundler.file_count))
        self.line("")
        self.line("    " + self.relative(bundler.target) + os.sep)
        self.line("")

        for note in bundler.notes:
            self.output.bullet(note)

        if bundler.warnings:
            self.line("")

            for warning in bundler.warnings:
                self.warn("  ! " + warning)

        self.line("")
        self.comment("  Read " + self.relative(bundler.target) + "/DEPLOY.md before uploading.")
        self.line("")
