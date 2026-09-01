<?php

declare(strict_types=1);

namespace App\Models;

use Bazimya\Database\Model;

class User extends Model
{
    protected string $table = 'users';

    protected array $fillable = ['name', 'email', 'password'];

    /** Never leak the hash in toArray() or JSON responses. */
    protected array $hidden = ['password'];
}
