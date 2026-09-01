<?php

declare(strict_types=1);

namespace Bazimya\Database;

/**
 * Base class for migrations.
 *
 * Bazimya 0.1 migrations are written in SQL. A schema builder is planned, but
 * raw SQL keeps the surface honest and portable for now.
 */
abstract class Migration
{
    protected Connection $db;

    public function setConnection(Connection $connection): void
    {
        $this->db = $connection;
    }

    abstract public function up(): void;

    abstract public function down(): void;

    /** @param array<int|string, mixed> $bindings */
    protected function execute(string $sql, array $bindings = []): void
    {
        $this->db->statement($sql, $bindings);
    }

    protected function connection(): Connection
    {
        return $this->db;
    }
}
