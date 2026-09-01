<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;

class CacheClearCommand extends Command
{
    public static string $name = 'cache:clear';

    public static string $description = 'Clear the compiled view cache';

    public static string $usage = 'bazimya cache:clear';

    public function handle(): int
    {
        $cleared = $this->app()->make('view')->clearCache();

        $this->line('');
        $this->success('  Cleared ' . $cleared . ' compiled view' . ($cleared === 1 ? '' : 's') . '.');
        $this->line('');

        return 0;
    }
}
