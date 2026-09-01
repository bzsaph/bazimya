<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class MakeMigrationCommand extends Command
{
    public static string $name = 'make:migration';

    public static string $description = 'Create a new migration file';

    public static string $usage = 'bazimya make:migration <name>';

    public function handle(): int
    {
        $name = $this->argument(0);

        if ($name === null) {
            $this->error('Please name the migration, e.g. bazimya make:migration create_users_table');

            return 1;
        }

        $name = $this->snake($name);
        $filename = date('Y_m_d_His') . '_' . $name;
        $path = $this->app()->databasePath('migrations/' . $filename . '.php');

        // Guess the table so the stub arrives half-written.
        $table = 'table_name';
        if (preg_match('/^create_(.+)_table$/', $name, $matches) === 1) {
            $table = $matches[1];
        } elseif (preg_match('/_(?:to|from|in)_(.+)_table$/', $name, $matches) === 1) {
            $table = $matches[1];
        }

        $contents = $this->renderStub('migration', [
            'table' => $table,
            'name' => $name,
        ]);

        if (! $this->writeFile($path, $contents, $this->flag('force'))) {
            return 1;
        }

        $this->success('Created ' . $this->relative($path));

        return 0;
    }
}
