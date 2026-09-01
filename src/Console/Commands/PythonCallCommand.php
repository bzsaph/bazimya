<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use Bazimya\Python\PythonBridge;

class PythonCallCommand extends Command
{
    public static string $name = 'python:call';

    public static string $description = 'Call a Python service directly from the CLI';

    public static string $usage = 'bazimya python:call <Service> [--key=value ...]';

    public function handle(): int
    {
        $service = $this->argument(0);

        if ($service === null) {
            $this->error('Please name the service, e.g. bazimya python:call ExampleService --message=Hi');

            return 1;
        }

        /** @var PythonBridge $python */
        $python = $this->app()->make('python');

        // Every --option becomes a payload key.
        $payload = [];
        foreach ($this->opts as $key => $value) {
            $payload[$key] = $value;
        }

        $this->line('');
        $this->comment("  Calling {$service}...");
        $this->line('');

        $result = $python->call($service, $payload);

        $this->line(json_encode($result, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE) ?: '');
        $this->line('');

        return 0;
    }
}
