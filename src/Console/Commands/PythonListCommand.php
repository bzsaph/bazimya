<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use Bazimya\Python\PythonBridge;

class PythonListCommand extends Command
{
    public static string $name = 'python:list';

    public static string $description = 'List the available Python services';

    public static string $usage = 'bazimya python:list';

    public function handle(): int
    {
        /** @var PythonBridge $python */
        $python = $this->app()->make('python');

        $services = $python->services();
        $version = $python->version();

        $this->line('');
        $this->comment('  Interpreter: ' . ($version ?? 'not found on PATH'));
        $this->line('');

        if ($services === []) {
            $this->comment('  No Python services yet. Create one:');
            $this->line('');
            $this->line('      bazimya make:python-service AIService');
            $this->line('');

            return 0;
        }

        foreach ($services as $service) {
            $this->line('  ' . $service);
        }

        $this->line('');
        $this->comment('  ' . count($services) . ' service' . (count($services) === 1 ? '' : 's'));
        $this->line('');

        return 0;
    }
}
