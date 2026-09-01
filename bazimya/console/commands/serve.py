"""bazimya serve — the development server."""

import os

from ... import serving
from ..command import Command


class ServeCommand(Command):
    name = "serve"

    description = "Run the development server"

    usage = "bazimya serve [--host=127.0.0.1] [--port=8000] [--no-reload]"

    def handle(self):
        application = self.application()

        host = str(self.option("host", "127.0.0.1"))
        port = int(self.option("port", 8000) or 8000)

        # The parent process only watches files; the child serves. Without
        # this check the child would fork another watcher, forever.
        if not self.flag("no-reload") and not serving.is_reloader_child():
            self._banner(host, serving.first_free_port(host, port), reloading=True)

            return serving.run_with_reloader(application.base_path)

        port = serving.first_free_port(host, port)

        if serving.is_reloader_child():
            # The banner was printed by the parent; printing it again on every
            # restart would bury the request log.
            pass
        else:
            self._banner(host, port, reloading=False)

        os.environ.setdefault("BAZIMYA_SERVING", "1")

        return serving.serve(
            application,
            host=host,
            port=port,
            public_directory=application.public_path(),
        )

    def _banner(self, host, port, reloading):
        display = "127.0.0.1" if host == "0.0.0.0" else host

        self.line("")
        self.info("  Bazimya development server")
        self.line("")
        self.line("  Local:     http://{}:{}".format(display, port))

        if host == "0.0.0.0":
            self.comment("  Network:   listening on every interface")

        self.comment("  Public:    " + self.relative(self.application().public_path()))
        self.comment("  Reload:    " + ("on" if reloading else "off"))
        self.line("")
        self.comment("  Press Ctrl+C to stop.")
        self.line("")
