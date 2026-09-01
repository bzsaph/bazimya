<?php

declare(strict_types=1);

namespace Bazimya\Foundation;

use Closure;
use RuntimeException;

/**
 * A deliberately small service container.
 *
 * Bazimya does not do autowiring by reflection — bindings are explicit
 * closures. It keeps resolution predictable and the framework readable.
 */
class Container
{
    /** @var array<string, array{factory: Closure, shared: bool}> */
    protected array $bindings = [];

    /** @var array<string, mixed> */
    protected array $instances = [];

    public function bind(string $key, Closure $factory, bool $shared = false): void
    {
        $this->bindings[$key] = ['factory' => $factory, 'shared' => $shared];
        unset($this->instances[$key]);
    }

    public function singleton(string $key, Closure $factory): void
    {
        $this->bind($key, $factory, true);
    }

    public function instance(string $key, mixed $object): void
    {
        $this->instances[$key] = $object;
    }

    public function has(string $key): bool
    {
        return isset($this->bindings[$key]) || isset($this->instances[$key]);
    }

    public function make(string $key): mixed
    {
        if (isset($this->instances[$key])) {
            return $this->instances[$key];
        }

        if (! isset($this->bindings[$key])) {
            throw new RuntimeException("Nothing is bound to [{$key}] in the container.");
        }

        $binding = $this->bindings[$key];
        $object = ($binding['factory'])($this);

        if ($binding['shared']) {
            $this->instances[$key] = $object;
        }

        return $object;
    }
}
