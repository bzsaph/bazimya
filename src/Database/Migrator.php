<?php

declare(strict_types=1);

namespace Bazimya\Database;

use RuntimeException;

/**
 * Runs migration files from database/migrations and records them in a
 * "migrations" table so each one runs exactly once.
 */
class Migrator
{
    public function __construct(
        protected Connection $connection,
        protected string $migrationPath,
    ) {
    }

    public function ensureMigrationsTable(): void
    {
        $sql = $this->connection->driver() === 'mysql'
            ? 'CREATE TABLE IF NOT EXISTS `migrations` (
                    `id` INT AUTO_INCREMENT PRIMARY KEY,
                    `migration` VARCHAR(255) NOT NULL,
                    `batch` INT NOT NULL
               )'
            : 'CREATE TABLE IF NOT EXISTS "migrations" (
                    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                    "migration" VARCHAR(255) NOT NULL,
                    "batch" INTEGER NOT NULL
               )';

        // Postgres has no AUTOINCREMENT keyword.
        if ($this->connection->driver() === 'pgsql') {
            $sql = 'CREATE TABLE IF NOT EXISTS "migrations" (
                        "id" SERIAL PRIMARY KEY,
                        "migration" VARCHAR(255) NOT NULL,
                        "batch" INTEGER NOT NULL
                   )';
        }

        $this->connection->statement($sql);
    }

    /** @return array<int, string> */
    public function ran(): array
    {
        $this->ensureMigrationsTable();

        return array_map(
            static fn (array $row): string => (string) $row['migration'],
            $this->connection->table('migrations')->orderBy('id')->get(),
        );
    }

    /** @return array<int, string> Absolute paths, sorted by filename. */
    public function pending(): array
    {
        $ran = $this->ran();
        $files = glob(rtrim($this->migrationPath, '/') . '/*.php') ?: [];

        sort($files);

        return array_values(array_filter(
            $files,
            static fn (string $file): bool => ! in_array(basename($file, '.php'), $ran, true),
        ));
    }

    /**
     * @return array<int, string> Names of the migrations that ran.
     */
    public function run(): array
    {
        $pending = $this->pending();

        if ($pending === []) {
            return [];
        }

        $batch = $this->nextBatch();
        $applied = [];

        foreach ($pending as $file) {
            $migration = $this->resolve($file);
            $migration->setConnection($this->connection);
            $migration->up();

            $name = basename($file, '.php');

            $this->connection->table('migrations')->insert([
                'migration' => $name,
                'batch' => $batch,
            ]);

            $applied[] = $name;
        }

        return $applied;
    }

    /**
     * Roll back the most recent batch.
     *
     * @return array<int, string>
     */
    public function rollback(): array
    {
        $this->ensureMigrationsTable();

        $batch = (int) ($this->connection->table('migrations')->orderBy('batch', 'desc')->value('batch') ?? 0);

        if ($batch === 0) {
            return [];
        }

        $rows = $this->connection->table('migrations')
            ->where('batch', $batch)
            ->orderBy('id', 'desc')
            ->get();

        $rolledBack = [];

        foreach ($rows as $row) {
            $name = (string) $row['migration'];
            $file = rtrim($this->migrationPath, '/') . '/' . $name . '.php';

            if (! is_file($file)) {
                throw new RuntimeException("Migration file for [{$name}] is missing.");
            }

            $migration = $this->resolve($file);
            $migration->setConnection($this->connection);
            $migration->down();

            $this->connection->table('migrations')->where('migration', $name)->delete();

            $rolledBack[] = $name;
        }

        return $rolledBack;
    }

    protected function nextBatch(): int
    {
        $max = $this->connection->table('migrations')->orderBy('batch', 'desc')->value('batch');

        return (int) ($max ?? 0) + 1;
    }

    protected function resolve(string $file): Migration
    {
        $migration = require $file;

        if (! $migration instanceof Migration) {
            throw new RuntimeException(
                'Migration ' . basename($file) . ' must return an instance of ' . Migration::class . '.',
            );
        }

        return $migration;
    }
}
