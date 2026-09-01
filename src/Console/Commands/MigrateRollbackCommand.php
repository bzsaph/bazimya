<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use Bazimya\Database\Migrator;

class MigrateRollbackCommand extends Command
{
    public static string $name = 'migrate:rollback';

    public static string $description = 'Roll back the last batch of migrations';

    public static string $usage = 'bazimya migrate:rollback';

    public function handle(): int
    {
        $app = $this->app();

        $migrator = new Migrator($app->make('db'), $app->databasePath('migrations'));

        $rolledBack = $migrator->rollback();

        $this->line('');

        if ($rolledBack === []) {
            $this->comment('  Nothing to roll back.');
            $this->line('');

            return 0;
        }

        foreach ($rolledBack as $name) {
            $this->line('  rolled back  ' . $name);
        }

        $this->line('');
        $this->success('  Rolled back ' . count($rolledBack) . ' migration' . (count($rolledBack) === 1 ? '' : 's') . '.');
        $this->line('');

        return 0;
    }
}
