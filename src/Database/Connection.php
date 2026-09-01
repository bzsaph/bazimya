<?php

declare(strict_types=1);

namespace Bazimya\Database;

use PDO;
use PDOException;
use RuntimeException;
use Throwable;

class Connection
{
    protected ?PDO $pdo = null;

    /**
     * @param array<string, mixed> $config
     */
    public function __construct(
        protected array $config,
        protected string $basePath = '',
    ) {
    }

    public function pdo(): PDO
    {
        if ($this->pdo instanceof PDO) {
            return $this->pdo;
        }

        $driver = (string) ($this->config['driver'] ?? 'sqlite');

        try {
            $this->pdo = match ($driver) {
                'sqlite' => $this->connectSqlite(),
                'mysql'  => $this->connectMysql(),
                'pgsql'  => $this->connectPgsql(),
                default  => throw new RuntimeException("Unsupported database driver [{$driver}]."),
            };
        } catch (PDOException $e) {
            throw new RuntimeException(
                "Bazimya could not connect to the [{$driver}] database: " . $e->getMessage(),
                previous: $e,
            );
        }

        $this->pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
        $this->pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
        $this->pdo->setAttribute(PDO::ATTR_EMULATE_PREPARES, false);

        return $this->pdo;
    }

    protected function connectSqlite(): PDO
    {
        $database = (string) ($this->config['database'] ?? 'database/database.sqlite');

        if ($database !== ':memory:' && ! str_starts_with($database, '/')) {
            $database = rtrim($this->basePath, '/') . '/' . ltrim($database, '/');
        }

        if ($database !== ':memory:') {
            $directory = dirname($database);

            if (! is_dir($directory)) {
                mkdir($directory, 0775, true);
            }

            if (! is_file($database)) {
                touch($database);
            }
        }

        $pdo = new PDO('sqlite:' . $database);
        $pdo->exec('PRAGMA foreign_keys = ON');

        return $pdo;
    }

    protected function connectMysql(): PDO
    {
        $dsn = sprintf(
            'mysql:host=%s;port=%s;dbname=%s;charset=%s',
            $this->config['host'] ?? '127.0.0.1',
            $this->config['port'] ?? 3306,
            $this->config['database'] ?? '',
            $this->config['charset'] ?? 'utf8mb4',
        );

        return new PDO($dsn, (string) ($this->config['username'] ?? ''), (string) ($this->config['password'] ?? ''));
    }

    protected function connectPgsql(): PDO
    {
        $dsn = sprintf(
            'pgsql:host=%s;port=%s;dbname=%s',
            $this->config['host'] ?? '127.0.0.1',
            $this->config['port'] ?? 5432,
            $this->config['database'] ?? '',
        );

        return new PDO($dsn, (string) ($this->config['username'] ?? ''), (string) ($this->config['password'] ?? ''));
    }

    public function driver(): string
    {
        return (string) ($this->config['driver'] ?? 'sqlite');
    }

    public function table(string $table): QueryBuilder
    {
        return new QueryBuilder($this, $table);
    }

    /**
     * @param array<int|string, mixed> $bindings
     * @return array<int, array<string, mixed>>
     */
    public function select(string $sql, array $bindings = []): array
    {
        $statement = $this->pdo()->prepare($sql);
        $statement->execute($bindings);

        return $statement->fetchAll();
    }

    /**
     * @param array<int|string, mixed> $bindings
     */
    public function statement(string $sql, array $bindings = []): int
    {
        $statement = $this->pdo()->prepare($sql);
        $statement->execute($bindings);

        return $statement->rowCount();
    }

    public function lastInsertId(): string
    {
        return $this->pdo()->lastInsertId();
    }

    public function transaction(callable $callback): mixed
    {
        $pdo = $this->pdo();
        $pdo->beginTransaction();

        try {
            $result = $callback($this);
            $pdo->commit();

            return $result;
        } catch (Throwable $e) {
            $pdo->rollBack();

            throw $e;
        }
    }
}
