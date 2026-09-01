<?php

declare(strict_types=1);

namespace Bazimya\Database;

use Bazimya\Foundation\Application;
use JsonSerializable;

/**
 * A thin active-record model.
 *
 * Bazimya models wrap the query builder rather than implementing a full ORM —
 * relationships are explicit methods, not magic.
 */
abstract class Model implements JsonSerializable
{
    /** Table name. Derived from the class name when left empty. */
    protected string $table = '';

    protected string $primaryKey = 'id';

    /** @var array<int, string> Columns that may be mass-assigned. */
    protected array $fillable = [];

    /** @var array<int, string> Columns hidden from toArray()/json. */
    protected array $hidden = [];

    protected bool $timestamps = true;

    /** @var array<string, mixed> */
    protected array $attributes = [];

    protected bool $exists = false;

    /** @param array<string, mixed> $attributes */
    public function __construct(array $attributes = [])
    {
        $this->fill($attributes);
    }

    /* ---------------------------------------------------------------------
     | Attributes
     * ------------------------------------------------------------------ */

    /** @param array<string, mixed> $attributes */
    public function fill(array $attributes): static
    {
        foreach ($attributes as $key => $value) {
            if ($this->fillable === [] || in_array($key, $this->fillable, true)) {
                $this->attributes[$key] = $value;
            }
        }

        return $this;
    }

    /** @param array<string, mixed> $attributes */
    public function forceFill(array $attributes): static
    {
        foreach ($attributes as $key => $value) {
            $this->attributes[$key] = $value;
        }

        return $this;
    }

    public function __get(string $key): mixed
    {
        return $this->attributes[$key] ?? null;
    }

    public function __set(string $key, mixed $value): void
    {
        $this->attributes[$key] = $value;
    }

    public function __isset(string $key): bool
    {
        return isset($this->attributes[$key]);
    }

    public function getKey(): mixed
    {
        return $this->attributes[$this->primaryKey] ?? null;
    }

    /** @return array<string, mixed> */
    public function toArray(): array
    {
        return array_diff_key($this->attributes, array_flip($this->hidden));
    }

    public function jsonSerialize(): mixed
    {
        return $this->toArray();
    }

    /* ---------------------------------------------------------------------
     | Table / connection plumbing
     * ------------------------------------------------------------------ */

    public function getTable(): string
    {
        if ($this->table !== '') {
            return $this->table;
        }

        $class = static::class;
        $base = substr($class, (int) strrpos($class, '\\') + 1);

        // PascalCase -> snake_case, then a naive plural.
        $snake = strtolower((string) preg_replace('/(?<!^)[A-Z]/', '_$0', $base));

        return $this->pluralize($snake);
    }

    protected function pluralize(string $word): string
    {
        if (str_ends_with($word, 'y') && ! preg_match('/[aeiou]y$/', $word)) {
            return substr($word, 0, -1) . 'ies';
        }

        if (preg_match('/(s|x|z|ch|sh)$/', $word) === 1) {
            return $word . 'es';
        }

        return $word . 's';
    }

    protected static function connection(): Connection
    {
        /** @var Connection $connection */
        $connection = Application::getInstance()->make('db');

        return $connection;
    }

    public static function query(): QueryBuilder
    {
        $model = new static();

        return static::connection()->table($model->getTable());
    }

    /* ---------------------------------------------------------------------
     | Retrieval
     * ------------------------------------------------------------------ */

    /** @return array<int, static> */
    public static function all(): array
    {
        return array_map(
            static fn (array $row): static => static::hydrate($row),
            static::query()->get(),
        );
    }

    public static function find(mixed $id): ?static
    {
        $model = new static();
        $row = static::query()->find($id, $model->primaryKey);

        return $row === null ? null : static::hydrate($row);
    }

    /** @return array<int, static> */
    public static function where(string $column, mixed $operator = null, mixed $value = null): array
    {
        $query = func_num_args() === 2
            ? static::query()->where($column, $operator)
            : static::query()->where($column, $operator, $value);

        return array_map(
            static fn (array $row): static => static::hydrate($row),
            $query->get(),
        );
    }

    /** @param array<string, mixed> $row */
    public static function hydrate(array $row): static
    {
        $model = new static();
        $model->forceFill($row);
        $model->exists = true;

        return $model;
    }

    /* ---------------------------------------------------------------------
     | Persistence
     * ------------------------------------------------------------------ */

    /** @param array<string, mixed> $attributes */
    public static function create(array $attributes): static
    {
        $model = new static($attributes);
        $model->save();

        return $model;
    }

    public function save(): bool
    {
        $attributes = $this->attributes;

        if ($this->timestamps) {
            $now = date('Y-m-d H:i:s');

            if (! $this->exists) {
                $attributes['created_at'] = $attributes['created_at'] ?? $now;
            }

            $attributes['updated_at'] = $now;
        }

        $query = static::connection()->table($this->getTable());

        if ($this->exists) {
            $key = $this->getKey();

            if ($key === null) {
                return false;
            }

            unset($attributes[$this->primaryKey]);
            $query->where($this->primaryKey, $key)->update($attributes);

            $this->attributes = array_merge($this->attributes, $attributes);

            return true;
        }

        $id = $query->insertGetId($attributes);

        $this->attributes = array_merge($attributes, [$this->primaryKey => $id]);
        $this->exists = true;

        return true;
    }

    public function delete(): bool
    {
        $key = $this->getKey();

        if (! $this->exists || $key === null) {
            return false;
        }

        $deleted = static::connection()
            ->table($this->getTable())
            ->where($this->primaryKey, $key)
            ->delete();

        $this->exists = false;

        return $deleted > 0;
    }
}
