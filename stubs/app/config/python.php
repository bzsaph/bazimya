<?php

declare(strict_types=1);

use Bazimya\Support\Env;

return [
    /*
     * The interpreter Bazimya invokes. Point this at a virtualenv to give your
     * services their own dependencies, e.g. python/.venv/bin/python.
     */
    'binary' => Env::get('PYTHON_BINARY', 'python3'),

    /* Seconds before a Python call is killed. */
    'timeout' => (int) Env::get('PYTHON_TIMEOUT', 60),
];
