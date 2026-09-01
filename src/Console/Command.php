<?php

declare(strict_types=1);

namespace Bazimya\Console;

use Bazimya\Foundation\Application;
use RuntimeException;

abstract class Command
{
    /** The command name, e.g. "make:controller". */
    public static string $name = '';

    public static string $description = '';

    /** Usage line shown by "bazimya help <command>". */
    public static string $usage = '';

    /** Set to false for commands that run outside a project (e.g. "new"). */
    public static bool $needsApplication = true;

    /** @var array<int, string> */
    protected array $args = [];

    /** @var array<string, string|bool> */
    protected array $opts = [];

    protected ?Application $app = null;

    protected Output $output;

    public function __construct()
    {
        $this->output = new Output();
    }

    /**
     * @param array<int, string> $args
     * @param array<string, string|bool> $opts
     */
    public function setInput(array $args, array $opts): void
    {
        $this->args = $args;
        $this->opts = $opts;
    }

    public function setApplication(?Application $app): void
    {
        $this->app = $app;
    }

    abstract public function handle(): int;

    /* ---------------------------------------------------------------------
     | Input helpers
     * ------------------------------------------------------------------ */

    protected function argument(int $index, ?string $default = null): ?string
    {
        return $this->args[$index] ?? $default;
    }

    /** @return array<int, string> */
    protected function arguments(): array
    {
        return $this->args;
    }

    protected function option(string $key, string|bool|null $default = null): string|bool|null
    {
        return $this->opts[$key] ?? $default;
    }

    protected function flag(string $key): bool
    {
        return isset($this->opts[$key]) && $this->opts[$key] !== false;
    }

    protected function app(): Application
    {
        if ($this->app === null) {
            throw new RuntimeException(
                'This command must be run from inside a Bazimya project directory.',
            );
        }

        return $this->app;
    }

    /* ---------------------------------------------------------------------
     | Output helpers
     * ------------------------------------------------------------------ */

    protected function line(string $message = ''): void
    {
        $this->output->line($message);
    }

    protected function info(string $message): void
    {
        $this->output->info($message);
    }

    protected function success(string $message): void
    {
        $this->output->success($message);
    }

    protected function warn(string $message): void
    {
        $this->output->warn($message);
    }

    protected function error(string $message): void
    {
        $this->output->error($message);
    }

    protected function comment(string $message): void
    {
        $this->output->comment($message);
    }

    /** @param array<int, string> $headers @param array<int, array<int, string>> $rows */
    protected function table(array $headers, array $rows): void
    {
        $this->output->table($headers, $rows);
    }

    protected function confirm(string $question, bool $default = false): bool
    {
        $suffix = $default ? '[Y/n]' : '[y/N]';
        $this->output->write("{$question} {$suffix} ");

        $answer = trim((string) fgets(STDIN));

        if ($answer === '') {
            return $default;
        }

        return in_array(strtolower($answer), ['y', 'yes'], true);
    }

    /* ---------------------------------------------------------------------
     | Filesystem helpers used by the make: commands
     * ------------------------------------------------------------------ */

    /**
     * Absolute path to the installed framework package.
     *
     * Derived from this file's own location rather than a constant set by the
     * entry script, so it resolves identically whether the CLI was started via
     * the global binary, the project-local ./bazimya, or a test harness.
     */
    protected function packageRoot(): string
    {
        return dirname(__DIR__, 2);
    }

    protected function stub(string $name): string
    {
        $path = $this->packageRoot() . '/stubs/' . $name . '.stub';

        if (! is_file($path)) {
            throw new RuntimeException("Stub [{$name}] not found at {$path}.");
        }

        return (string) file_get_contents($path);
    }

    /** @param array<string, string> $replacements */
    protected function renderStub(string $name, array $replacements): string
    {
        $contents = $this->stub($name);

        foreach ($replacements as $key => $value) {
            $contents = str_replace('{{' . $key . '}}', $value, $contents);
        }

        return $contents;
    }

    protected function writeFile(string $path, string $contents, bool $force = false): bool
    {
        if (is_file($path) && ! $force) {
            $this->error('Already exists: ' . $this->relative($path));

            return false;
        }

        $directory = dirname($path);

        if (! is_dir($directory)) {
            mkdir($directory, 0775, true);
        }

        file_put_contents($path, $contents);

        return true;
    }

    protected function relative(string $path): string
    {
        $base = $this->app?->basePath() ?? getcwd();

        if ($base !== false && str_starts_with($path, $base)) {
            return ltrim(substr($path, strlen($base)), '/');
        }

        return $path;
    }

    protected function studly(string $value): string
    {
        $value = str_replace(['-', '_'], ' ', $value);

        return str_replace(' ', '', ucwords($value));
    }

    protected function snake(string $value): string
    {
        $value = (string) preg_replace('/(?<!^)[A-Z]/', '_$0', $value);

        return strtolower(str_replace(['-', ' '], '_', $value));
    }
}
