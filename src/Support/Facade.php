<?php

declare(strict_types=1);

namespace Bazimya\Support;

use Bazimya\Foundation\Application;

/**
 * Static proxy to a container binding, so routes and controllers can read as
 * Route::get(...) / View::render(...) instead of threading instances around.
 */
abstract class Facade
{
    /** The container key this facade resolves. */
    abstract protected static function accessor(): string;

    public static function __callStatic(string $method, array $arguments): mixed
    {
        $instance = Application::getInstance()->make(static::accessor());

        return $instance->{$method}(...$arguments);
    }
}
