<?php

declare(strict_types=1);

use Bazimya\Support\Env;

return [
    'name' => Env::get('APP_NAME', 'Bazimya'),

    'env' => Env::get('APP_ENV', 'local'),

    /*
     * When true, uncaught exceptions render with a stack trace.
     * Always false in production.
     */
    'debug' => (bool) Env::get('APP_DEBUG', true),

    'url' => Env::get('APP_URL', 'http://127.0.0.1:8000'),

    'key' => Env::get('APP_KEY', ''),

    'timezone' => Env::get('APP_TIMEZONE', 'UTC'),
];
