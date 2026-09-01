<?php

declare(strict_types=1);

namespace Bazimya\Facades;

use Bazimya\Support\Facade;

/**
 * @method static \Bazimya\Database\QueryBuilder table(string $table)
 * @method static array select(string $sql, array $bindings = [])
 * @method static int statement(string $sql, array $bindings = [])
 * @method static mixed transaction(callable $callback)
 * @method static \PDO pdo()
 */
class DB extends Facade
{
    protected static function accessor(): string
    {
        return 'db';
    }
}
