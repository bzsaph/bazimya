<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use Bazimya\Http\Route;

class RouteListCommand extends Command
{
    public static string $name = 'route:list';

    public static string $description = 'List the registered routes';

    public static string $usage = 'bazimya route:list';

    public function handle(): int
    {
        $app = $this->app()->boot();

        /** @var array<int, Route> $routes */
        $routes = $app->make('router')->routes();

        if ($routes === []) {
            $this->line('');
            $this->comment('  No routes are registered. Add some in routes/web.php.');
            $this->line('');

            return 0;
        }

        $rows = [];

        foreach ($routes as $route) {
            $methods = array_values(array_diff($route->methods(), ['HEAD']));

            $rows[] = [
                implode('|', $methods),
                $route->uri(),
                $this->describeAction($route->action()),
                $route->getName() ?? '',
            ];
        }

        $this->line('');
        $this->table(['METHOD', 'URI', 'ACTION', 'NAME'], $rows);
        $this->line('');
        $this->comment('  ' . count($routes) . ' route' . (count($routes) === 1 ? '' : 's'));
        $this->line('');

        return 0;
    }

    protected function describeAction(mixed $action): string
    {
        if ($action instanceof \Closure) {
            return 'Closure';
        }

        if (is_array($action)) {
            [$class, $method] = $action;
            $short = substr((string) $class, (int) strrpos((string) $class, '\\') + 1);

            return $short . '@' . $method;
        }

        return is_string($action) ? $action : 'callable';
    }
}
