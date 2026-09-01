"""Service providers.

The same two-phase contract as Laravel's: `register` only puts things in the
container, `boot` may use them. Keeping registration free of resolution is
what allows any provider to depend on any other.

    class AppServiceProvider(ServiceProvider):
        def register(self):
            self.app.singleton('payments', lambda c: PaymentGateway())

        def boot(self):
            View.share('app_name', self.config('app.name'))
"""


class ServiceProvider:
    def __init__(self, application):
        self.app = application

    def register(self):
        """Bind things into the container. Do not resolve anything here."""

    def boot(self):
        """Runs after every provider has registered."""

    # -- helpers ----------------------------------------------------------

    def config(self, key, default=None):
        return self.app.make("config").get(key, default)

    def load_routes_from(self, path, attributes=None):
        """Register another route file, optionally inside a group."""
        import importlib.util
        import os
        import sys

        if not os.path.isfile(path):
            return self

        module_name = "bazimya_routes_" + os.path.basename(path)[:-3]

        def load():
            spec = importlib.util.spec_from_file_location(module_name, path)

            if spec is None or spec.loader is None:
                return

            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)

        if attributes:
            self.app.make("router").group(attributes, load)
        else:
            load()

        return self

    def load_views_from(self, path, namespace):
        self.app.make("view").add_namespace(namespace, path)

        return self

    def load_migrations_from(self, path):
        """Migrations registered here are picked up by `bazimya migrate`."""
        self.app.add_migration_path(path)

        return self
