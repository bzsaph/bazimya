# Bazimya

A PHP framework with first-class Python services.

Bazimya borrows the architectural ideas that make Laravel pleasant — a container,
expressive routing, a template engine, migrations, a generator CLI — and adds one
thing PHP frameworks usually leave to glue code: **calling Python from PHP as a
normal part of the application**.

```php
use Bazimya\Facades\Python;

$result = Python::call('AIService', ['message' => 'Hello']);
```

**Status: 0.1.0.** The API works and is tested end to end, but it will change
before 1.0. Not recommended for production yet.

---

## Requirements

- PHP 8.2+ with `pdo` and `json`
- Composer
- Python 3.8+ (only if you use Python services)

## Installation

Bazimya is not on Packagist yet, so install it from source:

```bash
git clone <your-repo-url> bazimya
cd bazimya
composer install
```

Then put the CLI on your PATH:

```bash
ln -s "$(pwd)/bin/bazimya" /usr/local/bin/bazimya
```

Once published, this becomes:

```bash
composer global require bazimya/bazimya
```

## Creating an application

```bash
bazimya new blog
cd blog
bazimya serve
```

Open <http://127.0.0.1:8000>.

Inside a project you can use the global `bazimya` or the local `php bazimya` —
both run the same CLI.

## Project layout

```
blog/
├── app/
│   ├── Controllers/
│   └── Models/
├── config/            app.php, database.php, python.php
├── database/
│   └── migrations/
├── public/            document root; index.php is the front controller
├── python/
│   ├── bazimya_bridge.py
│   └── services/      one file per Python service
├── resources/
│   └── views/         *.bazimya.php templates
├── routes/
│   └── web.php
├── storage/           compiled views, logs
├── .env
├── bazimya            project-local CLI
└── server.php         dev-server router
```

## Routing

```php
use Bazimya\Facades\Route;

Route::get('/', [HomeController::class, 'index'])->name('home');
Route::post('/posts', [PostController::class, 'store']);
Route::get('/posts/{id}', [PostController::class, 'show']);
Route::get('/hello/{name?}', fn ($request, $name = null) => "Hi {$name}");

Route::group(['prefix' => 'api', 'middleware' => [EnsureToken::class]], function () {
    Route::get('/status', fn () => ['status' => 'ok']);
});
```

Return a `Response`, a string, or an array (arrays become JSON automatically).

Middleware is any class with a `handle` method:

```php
class EnsureToken implements Bazimya\Http\Middleware
{
    public function handle(Request $request, Closure $next): Response
    {
        if ($request->header('X-Token') !== 'secret') {
            return Response::json(['error' => 'Unauthorised'], 401);
        }

        return $next($request);
    }
}
```

## Views

Templates live in `resources/views` and end in `.bazimya.php`.

```php
@extends('layouts.app')

@section('title'){{ $title }}@endsection

@section('content')
    <h1>{{ $title }}</h1>

    @if (count($posts) > 0)
        @foreach ($posts as $post)
            <article>{{ $post['title'] }}</article>
        @endforeach
    @else
        <p>Nothing here yet.</p>
    @endif

    @include('partials.footer')
@endsection
```

`{{ }}` escapes, `{!! !!}` does not. Compiled templates are cached in
`storage/framework/views` and recompiled when the source changes.

## Database

SQLite by default — the file is created on first use, so there is nothing to
install. Change `DB_CONNECTION` in `.env` for MySQL or Postgres.

**Query builder:**

```php
use Bazimya\Facades\DB;

DB::table('users')->where('active', 1)->orderBy('name')->limit(10)->get();
DB::table('users')->insert(['name' => 'James', 'email' => 'j@example.com']);
DB::table('users')->where('id', 3)->update(['name' => 'James M.']);
```

**Models:**

```php
class User extends Bazimya\Database\Model
{
    protected string $table = 'users';
    protected array $fillable = ['name', 'email'];
    protected array $hidden = ['password'];
}

$user = User::create(['name' => 'James', 'email' => 'j@example.com']);
$user = User::find(1);
$user->name = 'James M.';
$user->save();
```

**Migrations** are plain SQL in 0.1:

```php
return new class extends Bazimya\Database\Migration {
    public function up(): void
    {
        $this->execute('CREATE TABLE "posts" ("id" INTEGER PRIMARY KEY AUTOINCREMENT)');
    }

    public function down(): void
    {
        $this->execute('DROP TABLE IF EXISTS "posts"');
    }
};
```

```bash
bazimya migrate
bazimya migrate:rollback
```

## Python services

A service is a file in `python/services/` exposing `handle(payload)`:

```python
# python/services/AIService.py
def handle(payload):
    return {"reply": "Hello from Python!", "got": payload.get("message")}
```

Call it from PHP:

```php
$result = Python::call('AIService', ['message' => 'Hello']);
// ['reply' => 'Hello from Python!', 'got' => 'Hello']
```

Or from the CLI:

```bash
bazimya python:call AIService --message=Hello
bazimya python:list
```

**How it works:** PHP runs `python3 python/bazimya_bridge.py <Service>`, writes
the payload as JSON to stdin, and reads a JSON envelope from stdout. Anything a
service `print`s is redirected to stderr so it cannot corrupt the response.

**Trade-off:** one process per call. That is simple and needs no daemon, port or
supervisor, but it pays interpreter startup (~30-50 ms) every time. A persistent
worker pool is planned; `Python::call()` will not change when it lands.

To give services their own dependencies, point `PYTHON_BINARY` at a virtualenv:

```
PYTHON_BINARY=python/.venv/bin/python
```

## CLI

```
bazimya new <name>                  Create a new application
bazimya serve [--host] [--port]     Development server
bazimya make:controller <Name>      [--resource]
bazimya make:model <Name>           [--migration]
bazimya make:migration <name>
bazimya make:python-service <Name>
bazimya migrate
bazimya migrate:rollback
bazimya route:list
bazimya python:call <Service> [--key=value]
bazimya python:list
bazimya cache:clear
```

## Publishing to Packagist

1. Push this repository to GitHub.
2. Tag a release: `git tag v0.1.0 && git push --tags`.
3. Submit the repo URL at <https://packagist.org/packages/submit>.
4. Add the GitHub webhook Packagist offers, so new tags publish automatically.

After that, `composer global require bazimya/bazimya` works, and generated apps
no longer need the `repositories` block in their `composer.json`.

## Roadmap

- Schema builder, so migrations stop being raw SQL
- Sessions, authentication and CSRF protection
- Persistent Python workers instead of process-per-call
- Validation
- A test harness for HTTP and CLI
- Relationships on models

## Licence

MIT.
