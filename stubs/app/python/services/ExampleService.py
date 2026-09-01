"""ExampleService — proves the PHP to Python bridge works.

Try it:

    bazimya python:call ExampleService --message=Hello

Or over HTTP, once the server is running:

    curl "http://127.0.0.1:8000/python?message=Hello"
"""

import platform


def handle(payload):
    message = payload.get("message", "")

    return {
        "received": message,
        "reply": "Hello from Python!",
        "python_version": platform.python_version(),
    }
