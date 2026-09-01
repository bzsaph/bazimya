<?php

declare(strict_types=1);

namespace Bazimya\Http;

/**
 * A single registered route.
 *
 * URIs use {param} for required segments and {param?} for optional ones:
 *
 *   /users/{id}
 *   /posts/{slug?}
 */
class Route
{
    protected ?string $name = null;

    /** @var array<int, class-string> */
    protected array $middleware = [];

    /** @var array<string, string> */
    protected array $parameters = [];

    protected ?string $compiled = null;

    /**
     * @param array<int, string> $methods
     * @param callable|array|string $action
     */
    public function __construct(
        protected array $methods,
        protected string $uri,
        protected mixed $action,
    ) {
        $uri = '/' . trim($uri, '/');
        $this->uri = $uri === '/' ? '/' : rtrim($uri, '/');
    }

    public function name(string $name): static
    {
        $this->name = $name;

        return $this;
    }

    /** @param class-string|array<int, class-string> $middleware */
    public function middleware(string|array $middleware): static
    {
        $this->middleware = array_merge($this->middleware, (array) $middleware);

        return $this;
    }

    public function getName(): ?string
    {
        return $this->name;
    }

    /** @return array<int, string> */
    public function methods(): array
    {
        return $this->methods;
    }

    public function uri(): string
    {
        return $this->uri;
    }

    public function action(): mixed
    {
        return $this->action;
    }

    /** @return array<int, class-string> */
    public function getMiddleware(): array
    {
        return $this->middleware;
    }

    /** @return array<string, string> */
    public function parameters(): array
    {
        return $this->parameters;
    }

    /**
     * Build a regex from the URI pattern, one segment at a time.
     *
     * Segment-by-segment is deliberate: escaping the whole URI first and then
     * un-escaping the placeholders is where routers usually pick up bugs.
     */
    protected function compile(): string
    {
        if ($this->compiled !== null) {
            return $this->compiled;
        }

        if ($this->uri === '/') {
            return $this->compiled = '/';
        }

        $pattern = '';

        foreach (explode('/', trim($this->uri, '/')) as $segment) {
            if (preg_match('/^\{([A-Za-z_][A-Za-z0-9_]*)(\?)?\}$/', $segment, $m) === 1) {
                $name = $m[1];
                $optional = ($m[2] ?? '') === '?';

                // An optional parameter absorbs the slash in front of it, so
                // that /posts/{slug?} matches both /posts and /posts/hello.
                $pattern .= $optional
                    ? '(?:/(?P<' . $name . '>[^/]+))?'
                    : '/(?P<' . $name . '>[^/]+)';

                continue;
            }

            $pattern .= '/' . preg_quote($segment, '#');
        }

        return $this->compiled = ($pattern === '' ? '/' : $pattern);
    }

    public function matches(string $path): bool
    {
        if (preg_match('#^' . $this->compile() . '$#', $path, $matches) !== 1) {
            return false;
        }

        $this->parameters = array_filter(
            $matches,
            static fn ($key): bool => ! is_int($key),
            ARRAY_FILTER_USE_KEY,
        );

        return true;
    }
}
