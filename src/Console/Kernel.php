<?php

declare(strict_types=1);

namespace Bazimya\Console;

use Bazimya\Console\Commands\CacheClearCommand;
use Bazimya\Console\Commands\MakeControllerCommand;
use Bazimya\Console\Commands\MakeMigrationCommand;
use Bazimya\Console\Commands\MakeModelCommand;
use Bazimya\Console\Commands\MakePythonServiceCommand;
use Bazimya\Console\Commands\MigrateCommand;
use Bazimya\Console\Commands\MigrateRollbackCommand;
use Bazimya\Console\Commands\NewCommand;
use Bazimya\Console\Commands\PythonCallCommand;
use Bazimya\Console\Commands\PythonListCommand;
use Bazimya\Console\Commands\RouteListCommand;
use Bazimya\Console\Commands\ServeCommand;
use Bazimya\Foundation\Application;
use Throwable;

class Kernel
{
    /** @var array<int, class-string<Command>> */
    protected array $commands = [
        NewCommand::class,
        ServeCommand::class,
        MakeControllerCommand::class,
        MakeModelCommand::class,
        MakeMigrationCommand::class,
        MakePythonServiceCommand::class,
        MigrateCommand::class,
        MigrateRollbackCommand::class,
        RouteListCommand::class,
        PythonCallCommand::class,
        PythonListCommand::class,
        CacheClearCommand::class,
    ];

    protected Output $output;

    public function __construct()
    {
        $this->output = new Output();
    }

    /** @param array<int, string> $argv */
    public function run(array $argv): int
    {
        $name = $argv[1] ?? null;

        if ($name === null || in_array($name, ['list', '--help', '-h', 'help'], true)) {
            $this->renderHelp();

            return 0;
        }

        if (in_array($name, ['--version', '-V', 'version'], true)) {
            $this->output->line('Bazimya ' . Application::VERSION);

            return 0;
        }

        $class = $this->resolve($name);

        if ($class === null) {
            $this->output->error("Unknown command \"{$name}\".");
            $this->suggest($name);

            return 1;
        }

        [$args, $opts] = $this->parseInput(array_slice($argv, 2));

        $command = new $class();
        $command->setInput($args, $opts);

        if ($class::$needsApplication) {
            $app = $this->bootApplication();

            if ($app === null) {
                $this->output->error('This does not look like a Bazimya project.');
                $this->output->line('');
                $this->output->line('  Run this command from a project directory, or create one:');
                $this->output->line('');
                $this->output->line('      bazimya new my-project');
                $this->output->line('');

                return 1;
            }

            $command->setApplication($app);
        }

        try {
            return $command->handle();
        } catch (Throwable $e) {
            $this->output->error($e->getMessage());

            if (getenv('BAZIMYA_DEBUG')) {
                $this->output->line($e->getTraceAsString());
            }

            return 1;
        }
    }

    /** @return class-string<Command>|null */
    protected function resolve(string $name): ?string
    {
        foreach ($this->commands as $class) {
            if ($class::$name === $name) {
                return $class;
            }
        }

        return null;
    }

    protected function suggest(string $name): void
    {
        $candidates = [];

        foreach ($this->commands as $class) {
            $distance = levenshtein($name, $class::$name);

            if ($distance <= 3 || str_contains($class::$name, $name)) {
                $candidates[] = $class::$name;
            }
        }

        if ($candidates !== []) {
            $this->output->line('');
            $this->output->line('Did you mean:');
            foreach ($candidates as $candidate) {
                $this->output->line('  ' . $candidate);
            }
        }

        $this->output->line('');
        $this->output->line('Run "bazimya list" to see every command.');
    }

    /**
     * Locate and bootstrap the project in (or above) the working directory.
     */
    protected function bootApplication(): ?Application
    {
        $directory = getcwd();

        if ($directory === false) {
            return null;
        }

        // Walk upwards so the CLI works from subdirectories too.
        while (true) {
            if (is_file($directory . '/bazimya') && is_dir($directory . '/routes')) {
                return new Application($directory);
            }

            $parent = dirname($directory);

            if ($parent === $directory) {
                return null;
            }

            $directory = $parent;
        }
    }

    /**
     * Split argv into positional arguments and --options.
     *
     * @param array<int, string> $input
     * @return array{0: array<int, string>, 1: array<string, string|bool>}
     */
    protected function parseInput(array $input): array
    {
        $args = [];
        $opts = [];

        foreach ($input as $token) {
            if (str_starts_with($token, '--')) {
                $token = substr($token, 2);

                if (str_contains($token, '=')) {
                    [$key, $value] = explode('=', $token, 2);
                    $opts[$key] = $value;
                } else {
                    $opts[$token] = true;
                }

                continue;
            }

            $args[] = $token;
        }

        return [$args, $opts];
    }

    protected function renderHelp(): void
    {
        $this->output->line('');
        $this->output->line('  ' . $this->output->bold('Bazimya') . ' ' . Application::VERSION);
        $this->output->line('  A PHP framework with first-class Python services.');
        $this->output->line('');
        $this->output->line('  ' . $this->output->bold('USAGE'));
        $this->output->line('      bazimya <command> [arguments] [--options]');
        $this->output->line('');
        $this->output->line('  ' . $this->output->bold('COMMANDS'));

        $groups = [];

        foreach ($this->commands as $class) {
            $group = str_contains($class::$name, ':')
                ? explode(':', $class::$name)[0]
                : 'general';

            $groups[$group][] = [$class::$name, $class::$description];
        }

        foreach ($groups as $group => $commands) {
            $this->output->line('');
            $this->output->comment('    ' . $group);

            $width = max(array_map(static fn (array $c): int => strlen($c[0]), $commands));

            foreach ($commands as [$name, $description]) {
                $this->output->line(
                    '      ' . str_pad($name, $width + 4) . $description,
                );
            }
        }

        $this->output->line('');
    }
}
