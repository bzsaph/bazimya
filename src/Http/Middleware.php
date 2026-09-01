<?php

declare(strict_types=1);

namespace Bazimya\Http;

use Closure;

/**
 * Contract for route middleware.
 *
 * Call $next($request) to continue down the stack, or return a Response to
 * short-circuit it.
 */
interface Middleware
{
    public function handle(Request $request, Closure $next): Response;
}
