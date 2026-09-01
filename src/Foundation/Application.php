<?php

declare(strict_types=1);

namespace Bazimya\Foundation;

use Bazimya\Database\Connection;
use Bazimya\Http\Request;
use Bazimya\Http\Response;
use Bazimya\Http\Router;
use Bazimya\Python\PythonBridge;
use Bazimya\Support\Config;
use Bazimya\Support\Env;
use Bazimya\View\View;
use Throwable;

/**
 * The Bazimya application: container, path resolution and the HTTP lifecycle.
 */
class Application extends Container
{
    public const VERSION = '0.1.0';

    protected static ?Application $instance = null;

    protected string $basePath;

    protected bool $booted = false;

    public function __construct(string $basePath)
    {
        $this->basePath = rtrim($basePath, '/');

        static::$instance = $this;

        Env::load($this->basePath('.env'));

        $this->registerCoreBindings();
    }

    public static function getInstance(): Application
    {
        if (static::$instance === null) {
            throw new \RuntimeException('No Bazimya application has been bootstrapped.');
        }

        return static::$instance;
    }

    public static function setInstance(?Application $app): void
    {
        static::$instance = $app;
    }

    protected function registerCoreBindings(): void
    {
        $this->instance('app', $this);

        $this->singleton('config', fn () => new Config($this->configPath()));

        $this->singleton('router', fn () => new Router());

        $this->singleton('view', fn (Container $c) => new View(
            $this->resourcePath('views'),
            $this->storagePath('framework/views'),
        ));

        $this->singleton('db', function (Container $c) {
            /** @var Config $config */
            $config = $c->make('config');
            $default = $config->get('database.default', 'sqlite');
            $connection = $config->get("database.connections.{$default}", []);

            return new Connection($connection, $this->basePath());
        });

        $this->singleton('python', function (Container $c) {
            /** @var Config $config */
            $config = $c->make('config');

            return new PythonBridge(
                $this->basePath('python'),
                (string) $config->get('python.binary', 'python3'),
                (int) $config->get('python.timeout', 60),
            );
        });
    }

    /* ---------------------------------------------------------------------
     | Paths
     * ------------------------------------------------------------------ */

    public function basePath(string $path = ''): string
    {
        return $this->basePath . ($path !== '' ? '/' . ltrim($path, '/') : '');
    }

    public function configPath(string $path = ''): string
    {
        return $this->basePath('config' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    public function storagePath(string $path = ''): string
    {
        return $this->basePath('storage' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    public function resourcePath(string $path = ''): string
    {
        return $this->basePath('resources' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    public function databasePath(string $path = ''): string
    {
        return $this->basePath('database' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    public function routesPath(string $path = ''): string
    {
        return $this->basePath('routes' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    public function pythonPath(string $path = ''): string
    {
        return $this->basePath('python' . ($path !== '' ? '/' . ltrim($path, '/') : ''));
    }

    /* ---------------------------------------------------------------------
     | Lifecycle
     * ------------------------------------------------------------------ */

    /**
     * Load the route files. Safe to call more than once.
     */
    public function boot(): static
    {
        if ($this->booted) {
            return $this;
        }

        $routeFile = $this->routesPath('web.php');

        if (is_file($routeFile)) {
            require $routeFile;
        }

        $this->booted = true;

        return $this;
    }

    /**
     * Handle the current HTTP request and emit the response.
     */
    public function run(): void
    {
        $this->boot();

        $request = Request::capture();

        try {
            /** @var Router $router */
            $router = $this->make('router');
            $response = $router->dispatch($request);
        } catch (Throwable $e) {
            $response = $this->renderException($e);
        }

        $response->send();
    }

    protected function renderException(Throwable $e): Response
    {
        /** @var Config $config */
        $config = $this->make('config');

        if ($config->get('app.debug', false)) {
            $body = sprintf(
                "<h1>%s</h1><p><strong>%s</strong></p><p>%s:%d</p><pre>%s</pre>",
                htmlspecialchars(get_class($e), ENT_QUOTES),
                htmlspecialchars($e->getMessage(), ENT_QUOTES),
                htmlspecialchars($e->getFile(), ENT_QUOTES),
                $e->getLine(),
                htmlspecialchars($e->getTraceAsString(), ENT_QUOTES),
            );

            return new Response($body, 500);
        }

        return new Response('<h1>500 — Server Error</h1>', 500);
    }

    public function version(): string
    {
        return static::VERSION;
    }
}
