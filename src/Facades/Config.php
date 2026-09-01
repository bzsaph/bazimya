<?php

declare(strict_types=1);

namespace Bazimya\Facades;

use Bazimya\Support\Facade;

/**
 * @method static mixed get(string $key, mixed $default = null)
 * @method static void set(string $key, mixed $value)
 * @method static array all()
 */
class Config extends Facade
{
    protected static function accessor(): string
    {
        return 'config';
    }
}
