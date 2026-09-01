<?php

declare(strict_types=1);

namespace Bazimya\Facades;

use Bazimya\Support\Facade;

/**
 * @method static \Bazimya\Http\Route get(string $uri, mixed $action)
 * @method static \Bazimya\Http\Route post(string $uri, mixed $action)
 * @method static \Bazimya\Http\Route put(string $uri, mixed $action)
 * @method static \Bazimya\Http\Route patch(string $uri, mixed $action)
 * @method static \Bazimya\Http\Route delete(string $uri, mixed $action)
 * @method static \Bazimya\Http\Route any(string $uri, mixed $action)
 * @method static void group(array $attributes, \Closure $callback)
 * @method static array routes()
 */
class Route extends Facade
{
    protected static function accessor(): string
    {
        return 'router';
    }
}
