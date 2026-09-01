<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use Bazimya\Database\Migrator;

class MigrateCommand extends Command
{
    public static string $name = 'migrate';

    public static string $description = 'Run the pending database migrations';

    public static string $usage = 'bazimya migrate';

    public function handle(): int
    {
        $app = $this->app();

        $migrator = new Migrator($app->make('db'), $app->databasePath('migrations'));

        $pending = $migrator->pending();

        if ($pending === []) {
            $this->line('');
            $this->comment('  Nothing to migrate.');
            $this->line('');

            return 0;
        }

        $this->line('');

        foreach ($pending as $file) {
            $this->line('  running  ' . basename($file, '.php'));
        }

        $applied = $migrator->run();

        $this->line('');
        $this->success('  Migrated ' . count($applied) . ' migration' . (count($applied) === 1 ? '' : 's') . '.');
        $this->line('');

        return 0;
    }
}
