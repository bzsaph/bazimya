"""Bridge between PHP and Bazimya's Python services.

PHP runs:

    python3 python/bazimya_bridge.py <ServiceName>

with a JSON payload on stdin. We import python/services/<ServiceName>.py, call
its handle(payload) function, and print a JSON envelope on stdout:

    {"ok": true,  "data": ...}
    {"ok": false, "error": "..."}

Only this envelope goes to stdout — anything a service prints is redirected to
stderr so it can never corrupt the response PHP parses.
"""

import importlib.util
import json
import os
import sys
import traceback

SERVICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "services")


def load_service(name):
    """Import services/<name>.py without requiring it to be a package."""
    path = os.path.join(SERVICES_DIR, name + ".py")

    if not os.path.isfile(path):
        raise ImportError("Service '{}' was not found at {}".format(name, path))

    spec = importlib.util.spec_from_file_location("bazimya_service_" + name, path)

    if spec is None or spec.loader is None:
        raise ImportError("Could not load service '{}'".format(name))

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    return module


def respond(envelope):
    sys.stdout.write(json.dumps(envelope))
    sys.stdout.flush()


def main():
    if len(sys.argv) < 2:
        respond({"ok": False, "error": "No service name was given."})
        return 1

    name = sys.argv[1]

    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except ValueError as error:
        respond({"ok": False, "error": "Invalid JSON payload: {}".format(error)})
        return 1

    # A service that print()s would otherwise land in the middle of our JSON.
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        module = load_service(name)

        if not hasattr(module, "handle"):
            raise AttributeError(
                "Service '{}' does not define handle(payload).".format(name)
            )

        data = module.handle(payload)
    except Exception as error:  # noqa: BLE001 - report everything back to PHP
        sys.stdout = real_stdout
        traceback.print_exc(file=sys.stderr)
        respond({"ok": False, "error": "{}: {}".format(type(error).__name__, error)})
        return 1

    sys.stdout = real_stdout

    try:
        respond({"ok": True, "data": data})
    except (TypeError, ValueError) as error:
        respond(
            {
                "ok": False,
                "error": "Service '{}' returned something JSON cannot encode: {}".format(
                    name, error
                ),
            }
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
