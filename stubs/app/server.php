<?php

declare(strict_types=1);

/*
 * Router script for PHP's built-in development server.
 *
 * Static files under public/ are served as-is; everything else is handed to
 * the front controller.
 */

$uri = urldecode((string) parse_url($_SERVER['REQUEST_URI'] ?? '/', PHP_URL_PATH));

if ($uri !== '/' && is_file(__DIR__ . '/public' . $uri)) {
    return false;
}

require __DIR__ . '/public/index.php';
