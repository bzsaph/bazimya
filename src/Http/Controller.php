<?php

declare(strict_types=1);

namespace Bazimya\Http;

/**
 * Convenience base class for application controllers.
 */
abstract class Controller
{
    protected function view(string $view, array $data = [], int $status = 200): Response
    {
        return Response::view($view, $data, $status);
    }

    protected function json(mixed $data, int $status = 200): Response
    {
        return Response::json($data, $status);
    }

    protected function redirect(string $to, int $status = 302): Response
    {
        return Response::redirect($to, $status);
    }

    protected function abort(int $status, string $message = ''): Response
    {
        return new Response($message !== '' ? $message : "<h1>{$status}</h1>", $status);
    }
}
