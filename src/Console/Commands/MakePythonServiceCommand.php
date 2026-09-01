<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class MakePythonServiceCommand extends Command
{
    public static string $name = 'make:python-service';

    public static string $description = 'Create a new Python service';

    public static string $usage = 'bazimya make:python-service <Name> [--force]';

    public function handle(): int
    {
        $name = $this->argument(0);

        if ($name === null) {
            $this->error('Please name the service, e.g. bazimya make:python-service AIService');

            return 1;
        }

        $class = $this->studly($name);
        $path = $this->app()->pythonPath('services/' . $class . '.py');

        $contents = $this->renderStub('python-service', ['name' => $class]);

        if (! $this->writeFile($path, $contents, $this->flag('force'))) {
            return 1;
        }

        $this->success('Created ' . $this->relative($path));
        $this->line('');
        $this->comment('  Call it from PHP with:');
        $this->line('');
        $this->line("      \$result = Python::call('{$class}', ['message' => 'Hello']);");
        $this->line('');
        $this->comment('  Or try it from the CLI:');
        $this->line('');
        $this->line("      bazimya python:call {$class} --message=Hello");
        $this->line('');

        return 0;
    }
}
