<?php

declare(strict_types=1);

namespace Bazimya\Python;

use RuntimeException;

/**
 * Calls Python services from PHP.
 *
 * A service is a file in python/services/<Name>.py exposing handle(payload)
 * and returning something JSON-serialisable. PHP sends the payload as JSON on
 * stdin and reads a JSON envelope back on stdout.
 *
 * Process-per-call is deliberate for 0.1: it needs no daemon, no port and no
 * supervision. A long-lived worker pool is the obvious next step, and the
 * public API here is designed not to change when that lands.
 */
class PythonBridge
{
    public function __construct(
        protected string $pythonPath,
        protected string $binary = 'python3',
        protected int $timeout = 60,
    ) {
    }

    /**
     * Invoke a Python service and return its decoded result.
     *
     * @param array<string, mixed> $payload
     * @return array<string, mixed>
     */
    public function call(string $service, array $payload = []): array
    {
        $bridge = rtrim($this->pythonPath, '/') . '/bazimya_bridge.py';

        if (! is_file($bridge)) {
            throw new RuntimeException(
                "The Python bridge is missing at {$bridge}. Was this project created with \"bazimya new\"?",
            );
        }

        if (! $this->serviceExists($service)) {
            throw new RuntimeException(
                "Python service [{$service}] not found in " . $this->servicePath() . '.',
            );
        }

        $json = json_encode($payload, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);

        if ($json === false) {
            throw new RuntimeException('The payload for [' . $service . '] could not be encoded as JSON.');
        }

        [$stdout, $stderr, $exitCode] = $this->runProcess(
            [$this->binary, $bridge, $service],
            $json,
        );

        if ($exitCode !== 0) {
            throw new RuntimeException(
                "Python service [{$service}] exited with code {$exitCode}: " . trim($stderr),
            );
        }

        $decoded = json_decode($stdout, true);

        if (! is_array($decoded)) {
            throw new RuntimeException(
                "Python service [{$service}] did not return JSON. Output was: " . trim($stdout),
            );
        }

        if (($decoded['ok'] ?? false) === false) {
            throw new RuntimeException(
                "Python service [{$service}] failed: " . (string) ($decoded['error'] ?? 'unknown error'),
            );
        }

        return is_array($decoded['data'] ?? null) ? $decoded['data'] : ['value' => $decoded['data'] ?? null];
    }

    /**
     * Run an arbitrary script in python/ and return raw stdout.
     *
     * @param array<int, string> $arguments
     */
    public function run(string $script, array $arguments = []): string
    {
        $path = rtrim($this->pythonPath, '/') . '/' . ltrim($script, '/');

        if (! is_file($path)) {
            throw new RuntimeException("Python script [{$script}] not found at {$path}.");
        }

        [$stdout, $stderr, $exitCode] = $this->runProcess(
            array_merge([$this->binary, $path], $arguments),
            null,
        );

        if ($exitCode !== 0) {
            throw new RuntimeException("Python script [{$script}] exited with code {$exitCode}: " . trim($stderr));
        }

        return $stdout;
    }

    public function servicePath(): string
    {
        return rtrim($this->pythonPath, '/') . '/services';
    }

    public function serviceExists(string $service): bool
    {
        return is_file($this->servicePath() . '/' . $service . '.py');
    }

    /** @return array<int, string> */
    public function services(): array
    {
        $files = glob($this->servicePath() . '/*.py') ?: [];

        return array_values(array_filter(array_map(
            static fn (string $file): string => basename($file, '.py'),
            $files,
        ), static fn (string $name): bool => ! str_starts_with($name, '__')));
    }

    public function version(): ?string
    {
        [$stdout, $stderr, $exitCode] = $this->runProcess([$this->binary, '--version'], null);

        if ($exitCode !== 0) {
            return null;
        }

        return trim($stdout !== '' ? $stdout : $stderr);
    }

    /**
     * @param array<int, string> $command
     * @return array{0: string, 1: string, 2: int}
     */
    protected function runProcess(array $command, ?string $input): array
    {
        $descriptors = [
            0 => ['pipe', 'r'],
            1 => ['pipe', 'w'],
            2 => ['pipe', 'w'],
        ];

        $process = proc_open($command, $descriptors, $pipes, $this->pythonPath);

        if (! is_resource($process)) {
            throw new RuntimeException("Unable to start [{$this->binary}]. Is Python installed and on your PATH?");
        }

        if ($input !== null) {
            fwrite($pipes[0], $input);
        }
        fclose($pipes[0]);

        stream_set_blocking($pipes[1], false);
        stream_set_blocking($pipes[2], false);

        $stdout = '';
        $stderr = '';
        $exitCode = -1;
        $deadline = microtime(true) + $this->timeout;

        while (true) {
            $stdout .= stream_get_contents($pipes[1]);
            $stderr .= stream_get_contents($pipes[2]);

            $status = proc_get_status($process);

            if (! $status['running']) {
                // Read the code here: once proc_get_status() has reaped the
                // child, proc_close() reports -1 instead of the real code.
                $exitCode = (int) $status['exitcode'];
                break;
            }

            if (microtime(true) > $deadline) {
                proc_terminate($process, 9);
                fclose($pipes[1]);
                fclose($pipes[2]);
                proc_close($process);

                throw new RuntimeException("The Python process timed out after {$this->timeout}s.");
            }

            usleep(2000);
        }

        // Drain anything buffered after the process exited.
        $stdout .= stream_get_contents($pipes[1]);
        $stderr .= stream_get_contents($pipes[2]);

        fclose($pipes[1]);
        fclose($pipes[2]);

        proc_close($process);

        return [$stdout, $stderr, $exitCode];
    }
}
