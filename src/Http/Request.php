<?php

declare(strict_types=1);

namespace Bazimya\Http;

class Request
{
    /** @var array<string, mixed> */
    protected array $routeParameters = [];

    public function __construct(
        protected string $method = 'GET',
        protected string $path = '/',
        protected array $query = [],
        protected array $body = [],
        protected array $headers = [],
        protected array $server = [],
        protected array $cookies = [],
    ) {
    }

    public static function capture(): static
    {
        $method = strtoupper($_SERVER['REQUEST_METHOD'] ?? 'GET');

        // Allow HTML forms to spoof PUT/PATCH/DELETE via a _method field.
        if ($method === 'POST' && isset($_POST['_method'])) {
            $spoofed = strtoupper((string) $_POST['_method']);
            if (in_array($spoofed, ['PUT', 'PATCH', 'DELETE'], true)) {
                $method = $spoofed;
            }
        }

        $uri = $_SERVER['REQUEST_URI'] ?? '/';
        $path = parse_url($uri, PHP_URL_PATH) ?: '/';

        $headers = [];
        foreach ($_SERVER as $key => $value) {
            if (str_starts_with($key, 'HTTP_')) {
                $name = str_replace(' ', '-', ucwords(strtolower(str_replace('_', ' ', substr($key, 5)))));
                $headers[$name] = $value;
            }
        }
        if (isset($_SERVER['CONTENT_TYPE'])) {
            $headers['Content-Type'] = $_SERVER['CONTENT_TYPE'];
        }

        $body = $_POST;

        // Merge a JSON payload into the body so input() works either way.
        $contentType = $headers['Content-Type'] ?? '';
        if (str_contains($contentType, 'application/json')) {
            $raw = file_get_contents('php://input') ?: '';
            $decoded = json_decode($raw, true);
            if (is_array($decoded)) {
                $body = array_merge($body, $decoded);
            }
        }

        return new static($method, rawurldecode($path), $_GET, $body, $headers, $_SERVER, $_COOKIE);
    }

    public function method(): string
    {
        return $this->method;
    }

    public function path(): string
    {
        $path = '/' . trim($this->path, '/');

        return $path === '/' ? '/' : rtrim($path, '/');
    }

    public function isMethod(string $method): bool
    {
        return $this->method === strtoupper($method);
    }

    public function input(string $key, mixed $default = null): mixed
    {
        return $this->body[$key] ?? $this->query[$key] ?? $default;
    }

    /** @return array<string, mixed> */
    public function all(): array
    {
        return array_merge($this->query, $this->body);
    }

    public function only(string ...$keys): array
    {
        return array_intersect_key($this->all(), array_flip($keys));
    }

    public function has(string $key): bool
    {
        return $this->input($key) !== null;
    }

    public function query(string $key, mixed $default = null): mixed
    {
        return $this->query[$key] ?? $default;
    }

    public function header(string $name, mixed $default = null): mixed
    {
        return $this->headers[$name] ?? $default;
    }

    public function cookie(string $name, mixed $default = null): mixed
    {
        return $this->cookies[$name] ?? $default;
    }

    public function wantsJson(): bool
    {
        $accept = (string) $this->header('Accept', '');

        return str_contains($accept, 'application/json');
    }

    /** @param array<string, mixed> $parameters */
    public function setRouteParameters(array $parameters): void
    {
        $this->routeParameters = $parameters;
    }

    public function parameter(string $key, mixed $default = null): mixed
    {
        return $this->routeParameters[$key] ?? $default;
    }

    /** @return array<string, mixed> */
    public function parameters(): array
    {
        return $this->routeParameters;
    }
}
