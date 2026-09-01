<?php

declare(strict_types=1);

use Bazimya\Database\Migration;

return new class extends Migration
{
    public function up(): void
    {
        $this->execute('
            CREATE TABLE IF NOT EXISTS "users" (
                "id" INTEGER PRIMARY KEY AUTOINCREMENT,
                "name" VARCHAR(255) NOT NULL,
                "email" VARCHAR(255) NOT NULL UNIQUE,
                "password" VARCHAR(255) NOT NULL,
                "created_at" DATETIME NULL,
                "updated_at" DATETIME NULL
            )
        ');
    }

    public function down(): void
    {
        $this->execute('DROP TABLE IF EXISTS "users"');
    }
};
