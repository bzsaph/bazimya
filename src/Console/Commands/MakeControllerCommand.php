<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class MakeControllerCommand extends Command
{
    public static string $name = 'make:controller';

    public static string $description = 'Create a new controller class';

    public static string $usage = 'bazimya make:controller <Name> [--resource] [--force]';

    public function handle(): int
    {
        $name = $this->argument(0);

        if ($name === null) {
            $this->error('Please provide a controller name, e.g. bazimya make:controller UserController');

            return 1;
        }

        $class = $this->studly($name);

        if (! str_ends_with($class, 'Controller')) {
            $class .= 'Controller';
        }

        $path = $this->app()->basePath('app/Controllers/' . $class . '.php');

        $contents = $this->renderStub(
            $this->flag('resource') ? 'controller.resource' : 'controller',
            ['class' => $class],
        );

        if (! $this->writeFile($path, $contents, $this->flag('force'))) {
            return 1;
        }

        $this->success('Created ' . $this->relative($path));

        return 0;
    }
}
