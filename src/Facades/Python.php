<?php

declare(strict_types=1);

namespace Bazimya\Facades;

use Bazimya\Support\Facade;

/**
 * @method static array call(string $service, array $payload = [])
 * @method static string run(string $script, array $arguments = [])
 * @method static array services()
 * @method static bool serviceExists(string $service)
 * @method static string|null version()
 */
class Python extends Facade
{
    protected static function accessor(): string
    {
        return 'python';
    }
}
