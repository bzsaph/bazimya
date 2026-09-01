<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class MakeModelCommand extends Command
{
    public static string $name = 'make:model';

    public static string $description = 'Create a new model class';

    public static string $usage = 'bazimya make:model <Name> [--migration] [--force]';

    public function handle(): int
    {
        $name = $this->argument(0);

        if ($name === null) {
            $this->error('Please provide a model name, e.g. bazimya make:model User');

            return 1;
        }

        $class = $this->studly($name);
        $path = $this->app()->basePath('app/Models/' . $class . '.php');

        $contents = $this->renderStub('model', [
            'class' => $class,
            'table' => $this->tableName($class),
        ]);

        if (! $this->writeFile($path, $contents, $this->flag('force'))) {
            return 1;
        }

        $this->success('Created ' . $this->relative($path));

        if ($this->flag('migration')) {
            $migration = new MakeMigrationCommand();
            $migration->setApplication($this->app());
            $migration->setInput(['create_' . $this->tableName($class) . '_table'], []);

            return $migration->handle();
        }

        return 0;
    }

    protected function tableName(string $class): string
    {
        $snake = $this->snake($class);

        if (str_ends_with($snake, 'y') && preg_match('/[aeiou]y$/', $snake) !== 1) {
            return substr($snake, 0, -1) . 'ies';
        }

        if (preg_match('/(s|x|z|ch|sh)$/', $snake) === 1) {
            return $snake . 'es';
        }

        return $snake . 's';
    }
}
