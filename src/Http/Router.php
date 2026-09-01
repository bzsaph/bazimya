<?php

declare(strict_types=1);

namespace Bazimya\Http;

use Closure;
use RuntimeException;

class Router
{
    /** @var array<int, Route> */
    protected array $routes = [];

    /** @var array<int, array{prefix: string, middleware: array<int, string>}> */
    protected array $groupStack = [];

    public function get(string $uri, mixed $action): Route
    {
        return $this->addRoute(['GET', 'HEAD'], $uri, $action);
    }

    public function post(string $uri, mixed $action): Route
    {
        return $this->addRoute(['POST'], $uri, $action);
    }

    public function put(string $uri, mixed $action): Route
    {
        return $this->addRoute(['PUT'], $uri, $action);
    }

    public function patch(string $uri, mixed $action): Route
    {
        return $this->addRoute(['PATCH'], $uri, $action);
    }

    public function delete(string $uri, mixed $action): Route
    {
        return $this->addRoute(['DELETE'], $uri, $action);
    }

    public function options(string $uri, mixed $action): Route
    {
        return $this->addRoute(['OPTIONS'], $uri, $action);
    }

    public function any(string $uri, mixed $action): Route
    {
        return $this->addRoute(['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'], $uri, $action);
    }

    /**
     * @param array{prefix?: string, middleware?: string|array<int, string>} $attributes
     */
    public function group(array $attributes, Closure $callback): void
    {
        $this->groupStack[] = [
            'prefix' => trim((string) ($attributes['prefix'] ?? ''), '/'),
            'middleware' => (array) ($attributes['middleware'] ?? []),
        ];

        $callback($this);

        array_pop($this->groupStack);
    }

    /** @param array<int, string> $methods */
    public function addRoute(array $methods, string $uri, mixed $action): Route
    {
        $prefix = '';
        $middleware = [];

        foreach ($this->groupStack as $group) {
            if ($group['prefix'] !== '') {
                $prefix .= '/' . $group['prefix'];
            }
            $middleware = array_merge($middleware, $group['middleware']);
        }

        $route = new Route($methods, $prefix . '/' . trim($uri, '/'), $action);

        if ($middleware !== []) {
            $route->middleware($middleware);
        }

        $this->routes[] = $route;

        return $route;
    }

    /** @return array<int, Route> */
    public function routes(): array
    {
        return $this->routes;
    }

    public function dispatch(Request $request): Response
    {
        $path = $request->path();
        $method = $request->method();
        $pathMatched = false;

        foreach ($this->routes as $route) {
            if (! $route->matches($path)) {
                continue;
            }

            $pathMatched = true;

            if (! in_array($method, $route->methods(), true)) {
                continue;
            }

            $request->setRouteParameters($route->parameters());

            return $this->runThroughMiddleware(
                $route,
                $request,
                fn (Request $req): Response => $this->toResponse(
                    $this->callAction($route->action(), $req, $route->parameters()),
                ),
            );
        }

        // A matching path with the wrong verb is a 405, not a 404.
        return $pathMatched
            ? new Response('<h1>405 — Method Not Allowed</h1>', 405)
            : $this->notFound();
    }

    protected function notFound(): Response
    {
        $app = \Bazimya\Foundation\Application::getInstance();

        /** @var \Bazimya\View\View $view */
        $view = $app->make('view');

        if ($view->exists('errors.404')) {
            return new Response($view->render('errors.404'), 404);
        }

        return new Response('<h1>404 — Not Found</h1>', 404);
    }

    /**
     * Run the route's middleware stack, innermost callback last.
     */
    protected function runThroughMiddleware(Route $route, Request $request, Closure $destination): Response
    {
        $pipeline = array_reduce(
            array_reverse($route->getMiddleware()),
            function (Closure $next, string $middleware): Closure {
                return function (Request $request) use ($middleware, $next): Response {
                    if (! class_exists($middleware)) {
                        throw new RuntimeException("Middleware [{$middleware}] was not found.");
                    }

                    return (new $middleware())->handle($request, $next);
                };
            },
            $destination,
        );

        return $pipeline($request);
    }

    /**
     * Supported action shapes: Closure, [Controller::class, 'method'],
     * 'Controller@method'.
     *
     * @param array<string, string> $parameters
     */
    protected function callAction(mixed $action, Request $request, array $parameters): mixed
    {
        if (is_string($action) && str_contains($action, '@')) {
            $action = explode('@', $action, 2);
        }

        if (is_array($action)) {
            [$class, $method] = $action;

            if (! class_exists($class)) {
                throw new RuntimeException("Controller [{$class}] was not found.");
            }

            $controller = new $class();

            if (! method_exists($controller, $method)) {
                throw new RuntimeException("Method [{$method}] not found on [{$class}].");
            }

            return $controller->{$method}($request, ...array_values($parameters));
        }

        if (is_callable($action)) {
            return $action($request, ...array_values($parameters));
        }

        throw new RuntimeException('The route action is not callable.');
    }

    protected function toResponse(mixed $result): Response
    {
        if ($result instanceof Response) {
            return $result;
        }

        if (is_array($result) || $result instanceof \JsonSerializable) {
            return Response::json($result);
        }

        return new Response((string) $result);
    }
}
