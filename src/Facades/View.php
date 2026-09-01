<?php

declare(strict_types=1);

namespace Bazimya\Facades;

use Bazimya\Support\Facade;

/**
 * @method static string render(string $view, array $data = [])
 * @method static bool exists(string $view)
 * @method static void share(string $key, mixed $value)
 * @method static int clearCache()
 */
class View extends Facade
{
    protected static function accessor(): string
    {
        return 'view';
    }
}
