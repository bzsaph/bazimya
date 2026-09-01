<?php

declare(strict_types=1);

use Bazimya\Support\Env;

return [
    /*
     * SQLite by default: no server to install, and the file is created on
     * first use. Switch DB_CONNECTION in .env to use MySQL or Postgres.
     */
    'default' => Env::get('DB_CONNECTION', 'sqlite'),

    'connections' => [
        'sqlite' => [
            'driver' => 'sqlite',
            // Relative paths resolve from the project root.
            'database' => Env::get('DB_DATABASE', 'database/database.sqlite'),
        ],

        'mysql' => [
            'driver' => 'mysql',
            'host' => Env::get('DB_HOST', '127.0.0.1'),
            'port' => Env::get('DB_PORT', '3306'),
            'database' => Env::get('DB_DATABASE', 'bazimya'),
            'username' => Env::get('DB_USERNAME', 'root'),
            'password' => Env::get('DB_PASSWORD', ''),
            'charset' => 'utf8mb4',
        ],

        'pgsql' => [
            'driver' => 'pgsql',
            'host' => Env::get('DB_HOST', '127.0.0.1'),
            'port' => Env::get('DB_PORT', '5432'),
            'database' => Env::get('DB_DATABASE', 'bazimya'),
            'username' => Env::get('DB_USERNAME', 'postgres'),
            'password' => Env::get('DB_PASSWORD', ''),
        ],
    ],
];
