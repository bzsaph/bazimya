<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class ServeCommand extends Command
{
    public static string $name = 'serve';

    public static string $description = 'Serve the application on the PHP development server';

    public static string $usage = 'bazimya serve [--host=127.0.0.1] [--port=8000]';

    public function handle(): int
    {
        $host = (string) $this->option('host', '127.0.0.1');
        $port = (int) $this->option('port', '8000');

        $base = $this->app()->basePath();
        $router = $base . '/server.php';
        $docroot = $base . '/public';

        if (! is_file($router)) {
            $this->error('server.php is missing from the project root.');

            return 1;
        }

        $port = $this->firstAvailablePort($host, $port);

        $this->line('');
        $this->info('  Bazimya development server');
        $this->line('');
        $this->line('  Local:   http://' . $host . ':' . $port);
        $this->comment('  Docroot: ' . $docroot);
        $this->line('');
        $this->comment('  Press Ctrl+C to stop.');
        $this->line('');

        $command = sprintf(
            '%s -S %s:%d -t %s %s',
            escapeshellarg(PHP_BINARY),
            escapeshellarg($host),
            $port,
            escapeshellarg($docroot),
            escapeshellarg($router),
        );

        passthru($command, $exitCode);

        return $exitCode;
    }

    /**
     * The PHP dev server dies immediately on a taken port, so step forward
     * until we find a free one rather than failing.
     */
    protected function firstAvailablePort(string $host, int $port): int
    {
        for ($candidate = $port; $candidate < $port + 20; $candidate++) {
            $socket = @fsockopen($host, $candidate, $errno, $errstr, 0.2);

            if ($socket === false) {
                return $candidate;
            }

            fclose($socket);

            $this->warn("  Port {$candidate} is in use, trying " . ($candidate + 1) . '...');
        }

        return $port;
    }
}
