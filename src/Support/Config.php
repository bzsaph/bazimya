<?php

declare(strict_types=1);

namespace Bazimya\Support;

/**
 * Loads every PHP file in config/ into a single dotted-key store.
 *
 * config/app.php returning ['name' => 'Bazimya'] becomes config('app.name').
 */
class Config
{
    /** @var array<string, mixed> */
    protected array $items = [];

    public function __construct(string $configPath)
    {
        if (! is_dir($configPath)) {
            return;
        }

        foreach (glob(rtrim($configPath, '/') . '/*.php') ?: [] as $file) {
            $key = basename($file, '.php');
            $values = require $file;

            if (is_array($values)) {
                $this->items[$key] = $values;
            }
        }
    }

    public function get(string $key, mixed $default = null): mixed
    {
        $segments = explode('.', $key);
        $value = $this->items;

        foreach ($segments as $segment) {
            if (! is_array($value) || ! array_key_exists($segment, $value)) {
                return $default;
            }
            $value = $value[$segment];
        }

        return $value;
    }

    public function set(string $key, mixed $value): void
    {
        $segments = explode('.', $key);
        $target = &$this->items;

        foreach ($segments as $segment) {
            if (! isset($target[$segment]) || ! is_array($target[$segment])) {
                $target[$segment] = [];
            }
            $target = &$target[$segment];
        }

        $target = $value;
    }

    /** @return array<string, mixed> */
    public function all(): array
    {
        return $this->items;
    }
}
