<?php

declare(strict_types=1);

namespace Bazimya\Database;

use InvalidArgumentException;

class QueryBuilder
{
    /** @var array<int, string> */
    protected array $columns = ['*'];

    /** @var array<int, array{boolean: string, sql: string}> */
    protected array $wheres = [];

    /** @var array<int, mixed> */
    protected array $bindings = [];

    /** @var array<int, string> */
    protected array $orders = [];

    protected ?int $limit = null;

    protected ?int $offset = null;

    protected const OPERATORS = ['=', '!=', '<>', '<', '<=', '>', '>=', 'like', 'not like', 'in', 'not in'];

    public function __construct(
        protected Connection $connection,
        protected string $table,
    ) {
    }

    public function select(string ...$columns): static
    {
        $this->columns = $columns === [] ? ['*'] : $columns;

        return $this;
    }

    /**
     * where('id', 5) or where('age', '>=', 18).
     */
    public function where(string $column, mixed $operator = null, mixed $value = null, string $boolean = 'and'): static
    {
        if (func_num_args() === 2) {
            $value = $operator;
            $operator = '=';
        }

        $operator = strtolower((string) $operator);

        if (! in_array($operator, self::OPERATORS, true)) {
            throw new InvalidArgumentException("Unsupported operator [{$operator}].");
        }

        $this->wheres[] = [
            'boolean' => $boolean,
            'sql' => $this->quote($column) . ' ' . strtoupper($operator) . ' ?',
        ];
        $this->bindings[] = $value;

        return $this;
    }

    public function orWhere(string $column, mixed $operator = null, mixed $value = null): static
    {
        return func_num_args() === 2
            ? $this->where($column, $operator, null, 'or')
            : $this->where($column, $operator, $value, 'or');
    }

    /** @param array<int, mixed> $values */
    public function whereIn(string $column, array $values, string $boolean = 'and'): static
    {
        if ($values === []) {
            $this->wheres[] = ['boolean' => $boolean, 'sql' => '1 = 0'];

            return $this;
        }

        $placeholders = implode(', ', array_fill(0, count($values), '?'));

        $this->wheres[] = [
            'boolean' => $boolean,
            'sql' => $this->quote($column) . " IN ({$placeholders})",
        ];

        foreach ($values as $value) {
            $this->bindings[] = $value;
        }

        return $this;
    }

    public function whereNull(string $column, string $boolean = 'and'): static
    {
        $this->wheres[] = ['boolean' => $boolean, 'sql' => $this->quote($column) . ' IS NULL'];

        return $this;
    }

    public function whereNotNull(string $column, string $boolean = 'and'): static
    {
        $this->wheres[] = ['boolean' => $boolean, 'sql' => $this->quote($column) . ' IS NOT NULL'];

        return $this;
    }

    public function orderBy(string $column, string $direction = 'asc'): static
    {
        $direction = strtolower($direction) === 'desc' ? 'DESC' : 'ASC';
        $this->orders[] = $this->quote($column) . ' ' . $direction;

        return $this;
    }

    public function limit(int $limit): static
    {
        $this->limit = $limit;

        return $this;
    }

    public function offset(int $offset): static
    {
        $this->offset = $offset;

        return $this;
    }

    /* ---------------------------------------------------------------------
     | Execution
     * ------------------------------------------------------------------ */

    /** @return array<int, array<string, mixed>> */
    public function get(): array
    {
        return $this->connection->select($this->toSql(), $this->bindings);
    }

    /** @return array<string, mixed>|null */
    public function first(): ?array
    {
        $rows = $this->limit(1)->get();

        return $rows[0] ?? null;
    }

    /** @return array<string, mixed>|null */
    public function find(mixed $id, string $column = 'id'): ?array
    {
        return $this->where($column, $id)->first();
    }

    public function value(string $column): mixed
    {
        $row = $this->select($column)->first();

        return $row[$column] ?? null;
    }

    public function count(): int
    {
        $sql = 'SELECT COUNT(*) AS aggregate FROM ' . $this->quote($this->table) . $this->compileWheres();
        $rows = $this->connection->select($sql, $this->bindings);

        return (int) ($rows[0]['aggregate'] ?? 0);
    }

    public function exists(): bool
    {
        return $this->count() > 0;
    }

    /** @param array<string, mixed> $values */
    public function insert(array $values): bool
    {
        $columns = implode(', ', array_map($this->quote(...), array_keys($values)));
        $placeholders = implode(', ', array_fill(0, count($values), '?'));

        $sql = 'INSERT INTO ' . $this->quote($this->table) . " ({$columns}) VALUES ({$placeholders})";

        return $this->connection->statement($sql, array_values($values)) > 0;
    }

    /** @param array<string, mixed> $values */
    public function insertGetId(array $values): int
    {
        $this->insert($values);

        return (int) $this->connection->lastInsertId();
    }

    /** @param array<string, mixed> $values */
    public function update(array $values): int
    {
        if ($values === []) {
            return 0;
        }

        $assignments = implode(', ', array_map(
            fn (string $column): string => $this->quote($column) . ' = ?',
            array_keys($values),
        ));

        $sql = 'UPDATE ' . $this->quote($this->table) . " SET {$assignments}" . $this->compileWheres();

        return $this->connection->statement($sql, array_merge(array_values($values), $this->bindings));
    }

    public function delete(): int
    {
        $sql = 'DELETE FROM ' . $this->quote($this->table) . $this->compileWheres();

        return $this->connection->statement($sql, $this->bindings);
    }

    /* ---------------------------------------------------------------------
     | Compilation
     * ------------------------------------------------------------------ */

    public function toSql(): string
    {
        $columns = implode(', ', array_map(
            fn (string $column): string => $column === '*' ? '*' : $this->quote($column),
            $this->columns,
        ));

        $sql = "SELECT {$columns} FROM " . $this->quote($this->table) . $this->compileWheres();

        if ($this->orders !== []) {
            $sql .= ' ORDER BY ' . implode(', ', $this->orders);
        }

        if ($this->limit !== null) {
            $sql .= ' LIMIT ' . $this->limit;
        }

        if ($this->offset !== null) {
            $sql .= ' OFFSET ' . $this->offset;
        }

        return $sql;
    }

    /** @return array<int, mixed> */
    public function bindings(): array
    {
        return $this->bindings;
    }

    protected function compileWheres(): string
    {
        if ($this->wheres === []) {
            return '';
        }

        $sql = '';

        foreach ($this->wheres as $index => $where) {
            $sql .= $index === 0
                ? ' WHERE '
                : ' ' . strtoupper($where['boolean']) . ' ';

            $sql .= $where['sql'];
        }

        return $sql;
    }

    /**
     * Identifier quoting. Column and table names never come from user input in
     * Bazimya's own code, but quoting keeps reserved words usable.
     */
    protected function quote(string $identifier): string
    {
        if (str_contains($identifier, '(') || $identifier === '*') {
            return $identifier;
        }

        $driver = $this->connection->driver();

        $wrap = static function (string $part) use ($driver): string {
            $part = str_replace(['`', '"'], '', $part);

            return $driver === 'mysql' ? "`{$part}`" : "\"{$part}\"";
        };

        return implode('.', array_map($wrap, explode('.', $identifier)));
    }
}
