<?php

declare(strict_types=1);

/*
 * Bazimya front controller. Every request enters here.
 */

define('BAZIMYA_START', microtime(true));

require dirname(__DIR__) . '/vendor/autoload.php';

$app = new Bazimya\Foundation\Application(dirname(__DIR__));

$app->run();
