<?php

declare(strict_types=1);

namespace Bazimya\Console;

class Output
{
    protected bool $colours;

    public function __construct()
    {
        // Respect NO_COLOR and skip escapes when piped to a file.
        $this->colours = getenv('NO_COLOR') === false
            && (! function_exists('stream_isatty') || @stream_isatty(STDOUT));
    }

    public function write(string $message): void
    {
        fwrite(STDOUT, $message);
    }

    public function line(string $message = ''): void
    {
        fwrite(STDOUT, $message . PHP_EOL);
    }

    public function info(string $message): void
    {
        $this->line($this->colour($message, '36'));
    }

    public function success(string $message): void
    {
        $this->line($this->colour($message, '32'));
    }

    public function warn(string $message): void
    {
        $this->line($this->colour($message, '33'));
    }

    public function comment(string $message): void
    {
        $this->line($this->colour($message, '90'));
    }

    public function error(string $message): void
    {
        fwrite(STDERR, $this->colour($message, '31') . PHP_EOL);
    }

    public function bold(string $message): string
    {
        return $this->colour($message, '1');
    }

    /**
     * @param array<int, string> $headers
     * @param array<int, array<int, string>> $rows
     */
    public function table(array $headers, array $rows): void
    {
        $widths = [];

        foreach ($headers as $index => $header) {
            $widths[$index] = mb_strlen($header);
        }

        foreach ($rows as $row) {
            foreach (array_values($row) as $index => $cell) {
                $widths[$index] = max($widths[$index] ?? 0, mb_strlen((string) $cell));
            }
        }

        $this->line($this->bold($this->formatRow($headers, $widths)));
        $this->line($this->colour($this->divider($widths), '90'));

        foreach ($rows as $row) {
            $this->line($this->formatRow(array_map(strval(...), array_values($row)), $widths));
        }
    }

    /** @param array<int, string> $cells @param array<int, int> $widths */
    protected function formatRow(array $cells, array $widths): string
    {
        $parts = [];

        foreach ($cells as $index => $cell) {
            $parts[] = $cell . str_repeat(' ', max(0, ($widths[$index] ?? 0) - mb_strlen($cell)));
        }

        return '  ' . rtrim(implode('  ', $parts));
    }

    /** @param array<int, int> $widths */
    protected function divider(array $widths): string
    {
        return '  ' . implode('  ', array_map(
            static fn (int $width): string => str_repeat('-', $width),
            $widths,
        ));
    }

    protected function colour(string $message, string $code): string
    {
        return $this->colours ? "\033[{$code}m{$message}\033[0m" : $message;
    }
}
