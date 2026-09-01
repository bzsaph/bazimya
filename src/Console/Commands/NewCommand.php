<?php

declare(strict_types=1);

namespace Bazimya\Console\Commands;

use Bazimya\Console\Command;
use RuntimeException;

class NewCommand extends Command
{
    public static string $name = 'new';

    public static string $description = 'Create a new Bazimya application';

    public static string $usage = 'bazimya new <name> [--force] [--no-install]';

    public static bool $needsApplication = false;

    public function handle(): int
    {
        $name = $this->argument(0);

        if ($name === null) {
            $this->error('Please give the application a name.');
            $this->line('');
            $this->line('    ' . static::$usage);
            $this->line('');

            return 1;
        }

        $target = str_starts_with($name, '/')
            ? $name
            : rtrim((string) getcwd(), '/') . '/' . $name;

        $appName = basename($target);

        if (is_dir($target) && ! $this->flag('force')) {
            $this->error("Directory [{$appName}] already exists. Use --force to overwrite.");

            return 1;
        }

        $this->line('');
        $this->info("  Creating a Bazimya application in {$appName}");
        $this->line('');

        $skeleton = $this->packageRoot() . '/stubs/app';

        if (! is_dir($skeleton)) {
            throw new RuntimeException("The application skeleton is missing at {$skeleton}.");
        }

        $this->copyDirectory($skeleton, $target);

        $this->writeComposerJson($target, $appName);
        $this->writeEnv($target, $appName);

        // These are gitignored in a real project, so they ship as .gitkeep and
        // need to exist for the first run.
        foreach (['storage/framework/views', 'storage/logs', 'database'] as $directory) {
            if (! is_dir($target . '/' . $directory)) {
                mkdir($target . '/' . $directory, 0775, true);
            }
        }

        chmod($target . '/bazimya', 0755);

        $this->success('  Application scaffolded.');

        if (! $this->flag('no-install')) {
            $this->line('');
            $this->comment('  Installing dependencies with Composer...');
            $this->line('');

            $exitCode = $this->composerInstall($target);

            if ($exitCode !== 0) {
                $this->line('');
                $this->warn('  Composer install did not finish cleanly.');
                $this->warn('  Run "composer install" inside ' . $appName . ' to retry.');
            }
        }

        $this->renderNextSteps($appName);

        return 0;
    }

    protected function copyDirectory(string $source, string $destination): void
    {
        if (! is_dir($destination)) {
            mkdir($destination, 0775, true);
        }

        $items = new \RecursiveIteratorIterator(
            new \RecursiveDirectoryIterator($source, \FilesystemIterator::SKIP_DOTS),
            \RecursiveIteratorIterator::SELF_FIRST,
        );

        foreach ($items as $item) {
            /** @var \SplFileInfo $item */
            $relative = substr($item->getPathname(), strlen($source) + 1);
            $targetPath = $destination . '/' . $relative;

            if ($item->isDir()) {
                if (! is_dir($targetPath)) {
                    mkdir($targetPath, 0775, true);
                }

                continue;
            }

            copy($item->getPathname(), $targetPath);
        }
    }

    /**
     * The generated composer.json points at the framework through a "path"
     * repository, so a new app works before bazimya/bazimya is on Packagist.
     * Once it is published, that repositories block can simply be deleted.
     */
    protected function writeComposerJson(string $target, string $appName): void
    {
        $manifest = [
            'name' => 'bazimya/' . $this->slug($appName),
            'description' => 'A Bazimya application.',
            'type' => 'project',
            'require' => [
                'php' => '>=8.2',
                'bazimya/bazimya' => '*',
            ],
            'autoload' => [
                'psr-4' => [
                    'App\\' => 'app/',
                ],
            ],
            'repositories' => [
                [
                    'type' => 'path',
                    'url' => $this->packageRoot(),
                    'options' => ['symlink' => true],
                ],
            ],
            'minimum-stability' => 'dev',
            'prefer-stable' => true,
            'config' => [
                'allow-plugins' => new \stdClass(),
            ],
        ];

        file_put_contents(
            $target . '/composer.json',
            json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n",
        );
    }

    protected function writeEnv(string $target, string $appName): void
    {
        $example = $target . '/.env.example';

        if (! is_file($example)) {
            return;
        }

        $contents = (string) file_get_contents($example);
        $contents = str_replace('{{app_name}}', $appName, $contents);
        $contents = str_replace('{{app_key}}', bin2hex(random_bytes(16)), $contents);

        file_put_contents($target . '/.env', $contents);
        file_put_contents($example, str_replace('{{app_key}}', '', $contents));
    }

    protected function composerInstall(string $target): int
    {
        $composer = $this->findComposer();

        if ($composer === null) {
            $this->warn('  Composer was not found on your PATH — skipping install.');

            return 1;
        }

        $command = sprintf(
            '%s install --working-dir=%s --no-interaction',
            escapeshellcmd($composer),
            escapeshellarg($target),
        );

        passthru($command, $exitCode);

        return $exitCode;
    }

    protected function findComposer(): ?string
    {
        $output = [];
        $status = 0;

        exec('command -v composer 2>/dev/null', $output, $status);

        return $status === 0 && isset($output[0]) ? $output[0] : null;
    }

    protected function slug(string $value): string
    {
        $slug = strtolower((string) preg_replace('/[^A-Za-z0-9]+/', '-', $value));

        return trim($slug, '-') ?: 'app';
    }

    protected function renderNextSteps(string $appName): void
    {
        $this->line('');
        $this->success('  Your Bazimya application is ready.');
        $this->line('');
        $this->comment('  Next steps:');
        $this->line('');
        $this->line("      cd {$appName}");
        $this->line('      bazimya serve');
        $this->line('');
        $this->comment('  Then open http://127.0.0.1:8000');
        $this->line('');
    }
}
