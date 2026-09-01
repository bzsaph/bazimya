"""Closure-style console commands, for routes/console.py.

    @Console.command('inspire', 'Display an inspiring quote')
    def inspire(args, options):
        return 'Simplicity is the ultimate sophistication.'

Laravel spells this `Artisan::command`. Anything longer than a few lines
belongs in a class under app/Console/Commands instead.
"""


class ConsoleRegistry:
    def __init__(self):
        self._commands = {}

    def command(self, name, description="", usage=None):
        """Register a command. The handler receives (args, options).

        Return a string to print it, or an int to use as the exit code.
        """

        def decorator(handler):
            self._commands[name] = {
                "name": name,
                "description": description,
                "usage": usage or "bazimya {}".format(name),
                "handler": handler,
            }

            return handler

        return decorator

    def all(self):
        return list(self._commands.values())

    def find(self, name):
        return self._commands.get(name)

    def reset(self):
        self._commands = {}


Console = ConsoleRegistry()
