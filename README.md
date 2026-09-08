# Bazimya

**A Python web framework with no dependencies.**

Controllers, models, migrations, templates, authentication and a CLI, in a
folder structure that stays the same in every project — `app/Http/Controllers`,
`routes/web`, `config/app`, `app/Console/Kernel`, `database/migrations`.
Templates end in `.baz.html`; the CLI is called `bazimya`.

It runs on the Python standard library alone, which is what lets it deploy to
shared hosting where you cannot run `pip` or open a shell.

```python
# routes/web.py
from bazimya import Route
from app.Http.Controllers import PostController

Route.get('/posts', [PostController, 'index']).name('posts.index')
Route.resource('posts', PostController)
```

```python
# app/Http/Controllers/PostController.py
from app.Models import Post

from .Controller import Controller


class PostController(Controller):
    def index(self, request):
        return self.view('posts.index', posts=Post.where('published', 1).latest().get())
```

```html
<!-- resources/views/posts/index.baz.html -->
@extends('layouts.app')

@section('content')
    @forelse post in posts
        <article>{{ post.title }}</article>
    @empty
        <p>Nothing here yet.</p>
    @endforelse
@endsection
```

**Status: 0.2.0.** Working and tested end to end, but pre-1.0 and still moving.
Not recommended for production yet.

---

## Requirements

- Python 3.8+
- Node 16+ *(optional — only for the `npx bazimya` wrapper)*

Nothing else. The framework runs on the standard library alone, which is what
makes it deployable to shared hosting where you cannot run `pip`.

## Install

```bash
npm install -g bazimya      # or: pip install bazimya
bazimya new blog
cd blog
bazimya migrate
bazimya serve
```

Open <http://127.0.0.1:8000>.

Inside a project you can use any of these — they all run the same code:

```bash
bazimya serve          # global install
npx bazimya serve      # npm, no install
npm run serve          # the script in package.json
python bazimya serve   # no Node at all
```

## Ikinyarwanda

Bazimya speaks English by default and Kinyarwanda when asked. Every
instruction, every label and every error message the framework produces goes
through one catalogue, so switching the language switches all of it:

```
bazimya lang rw     # Ikinyarwanda
bazimya lang        # show the current language
bazimya lang en     # back to English
```

```
$ bazimya lang rw
$ bazimya new urubuga

  Kurema porogaramu ya Bazimya muri urubuga

  Hakozwe dosiye 99.

  Ibikurikira:

      cd urubuga
      bazimya migrate
      bazimya serve
```

`bazimya lang` writes `APP_LOCALE` into the project's `.env`. Three other ways
to choose, in the order they are consulted:

| | |
|---|---|
| `BAZIMYA_LANG=rw bazimya serve` | one command only |
| `APP_LOCALE=rw` in `.env` | one project |
| `LANG=rw_RW.UTF-8` | the whole machine, already set on many Rwandan systems |

Validation messages follow the same setting, so the errors a **visitor** to
the site reads are in Kinyarwanda too:

```python
Validator({'email': 'nope'}, {'email': 'required|email'})
# rw: "email igomba kuba imeyili nyayo."
# en: "The email field must be a valid email address."
```

Names you have to type or find on disk stay in English on purpose —
`app/Models`, `migrate`, `.env`. Translating those would leave a beginner
reading an instruction they cannot follow.

### Adding a language

A catalogue is a dict keyed by the English sentence, so a missing entry falls
back to readable English rather than breaking. Add `bazimya/lang/sw.py` with a
`MESSAGES` dict, list `"sw"` in `bazimya.support.lang.SUPPORTED`, and translate
as much or as little as you like:

```python
MESSAGES = {
    "Next:": "Ifuatayo:",
    "Scaffolded {} files.": "Faili {} zimeundwa.",
}
```

Sentences the framework already filled in are matched back to their template,
so `{}` works whether the value is supplied before or after translation.

## Method names work either way

Bazimya's own methods are snake_case, but the camelCase spelling of each one
resolves to the same call, so either style reads correctly:

```python
User.where('active', 1).orderBy('name').firstOrFail()
User.where('active', 1).order_by('name').first_or_fail()  # identical
```

## Layout

```
blog/
├── app/
│   ├── Console/
│   │   ├── Commands/
│   │   └── Kernel.py           your CLI commands
│   ├── Exceptions/Handler.py
│   ├── Http/
│   │   ├── Controllers/
│   │   ├── Middleware/         Authenticate, VerifyCsrfToken, TrustProxies…
│   │   ├── Requests/           form requests
│   │   └── Kernel.py           middleware stacks, groups, aliases
│   ├── Models/
│   ├── Notifications/
│   ├── Providers/              App, Auth, Event, Route
│   ├── Rules/                  custom validation rules
│   ├── Services/
│   ├── Support/
│   └── View/Components/        <x-alert> and friends
├── bootstrap/app.py            builds the application
├── config/                     13 files, one per subsystem
├── database/
│   ├── factories/  migrations/  seeders/
├── extensions/                 drop-in packages
├── public/                     document root; index.py is the CGI fallback
├── resources/
│   ├── css/  js/
│   └── views/                  *.baz.html, incl. components/ and auth/
├── routes/                     web.py, api.py, auth.py, console.py
├── storage/                    sessions, cache, compiled views, logs
├── tests/                      TestCase.py, Feature/, Unit/
├── .env
├── bazimya                     the CLI
├── passenger_wsgi.py           cPanel entry point
└── wsgi.py                     gunicorn entry point
```

Controllers, models, middleware, requests and commands each live in a file
named after the class, and are importable straight away — nothing to register:

```python
from app.Http.Controllers import PostController
from app.Models import Post
```

## Routing

```python
from bazimya import Route

Route.get('/', [HomeController, 'index']).name('home')
Route.post('/posts', [PostController, 'store'])
Route.get('/posts/{id}', [PostController, 'show']).where_number('id')
Route.get('/posts/{slug?}', [PostController, 'show'])       # optional
Route.resource('posts', PostController)                     # the seven RESTful routes
Route.api_resource('posts', PostController)                 # minus create/edit

Route.middleware('auth').prefix('admin').name('admin.').group(lambda: [
    Route.get('/dashboard', [AdminController, 'index']).name('dashboard'),
])
```

Return a `Response`, a string, or a dict/list — dicts become JSON
automatically. Route parameters arrive as named arguments:

```python
def show(self, request, id):
    return {'id': id}
```

`routes/api.py` is loaded under `/api` with the `api` middleware group. Which
files load where is set in `app/Providers/RouteServiceProvider.py`.

### Middleware

```python
from bazimya import Middleware, Response


class EnsureToken(Middleware):
    def handle(self, request, next):
        if request.bearer_token() != 'secret':
            return Response.json({'error': 'Unauthorised'}, 401)

        return next(request)
```

Register it in `app/Http/Kernel.py` under `middleware`, `middleware_groups` or
`middleware_aliases`, then use it by name: `.middleware('auth')`.

## Views

Templates live in `resources/views` and end in `.baz.html`. Directives start
with `@`; every expression inside them is Python.

```html
@extends('layouts.app')

@section('title', 'Posts')

@section('content')
    <h1>{{ title }}</h1>

    @if len(posts) > 10
        <p>Quite a lot.</p>
    @elseif len(posts) > 0
        <p>A few.</p>
    @else
        <p>None.</p>
    @endif

    @foreach post in posts
        <article>{{ post.title }} — {{ post['author'] }}</article>
    @endforeach

    @forelse comment in comments
        <li>{{ comment.body }}</li>
    @empty
        <li>No comments.</li>
    @endforelse

    @include('partials.footer', {'year': 2026})
@endsection
```

`{{ }}` escapes, `{!! !!}` does not, `{{-- --}}` is a comment. Also available:
`@unless`, `@isset`, `@while`, `@each`, `@yield`, `@show`, `@parent`,
`@verbatim`, `@csrf`, `@method('PUT')`, `@json(data)`, `@dump(x)`, `@route`,
`@asset`, `@config`, and `@python … @endpython` for a block of real Python.

Templates compile to Python and are cached in `storage/framework/views`.

Writing `{{ $title }}` or `post->title` gives you a message naming the Python
spelling, rather than a syntax error.

### Components

`<x-alert>` renders a template from `resources/views/components/`, with an
optional class in `app/View/Components/` that prepares its data.

```html
<x-alert type="error" :count="len(errors)">
    Something went wrong.
</x-alert>

<x-input-error field="email" />
```

```python
# app/View/Components/Alert.py
class Alert(Component):
    def __init__(self, type='info'):
        self.type = type

    def classes(self):
        return 'alert alert-' + self.type
```

Attributes become constructor arguments; `:name="..."` evaluates a Python
expression in the surrounding template's scope; the inner content arrives as
`slot`. A template with no class works on its own.

```bash
bazimya make:component Badge            # class + template
bazimya make:component Badge --view-only
```

## Database

SQLite by default — the file is created on first use, so there is nothing to
install. Change `DB_CONNECTION` in `.env` for MySQL (`pip install PyMySQL`) or
Postgres (`pip install psycopg2-binary`).

**Query builder:**

```python
from bazimya import DB

DB.table('users').where('active', 1).order_by('name').limit(10).get()
DB.table('users').where('age', '>=', 18).count()
DB.table('users').insert({'name': 'James', 'email': 'j@example.com'})
DB.table('users').where('id', 3).update({'name': 'James M.'})
```

Values are always bound. Column and table names are validated as identifiers
rather than interpolated, so a column name arriving from request data cannot
become SQL.

**Models:**

```python
from bazimya import Model


class User(Model):
    table = 'users'
    fillable = ['name', 'email']
    hidden = ['password']
    casts = {'active': bool}


user = User.create({'name': 'James', 'email': 'j@example.com'})
user = User.find(1)
user.name = 'James M.'
user.save()

User.where('active', 1).order_by('name').get()
User.find_or_fail(3)
User.first_or_create({'email': 'a@b.c'}, {'name': 'Ada'})
User.paginate(page=2, per_page=15)
```

**Migrations** use a schema builder:

```python
from bazimya import Migration, Schema


class CreatePostsTable(Migration):
    def up(self):
        with Schema.create('posts') as table:
            table.id()
            table.string('title')
            table.text('body').nullable()
            table.foreign_id('user_id').references('id').on('users').on_delete('cascade')
            table.boolean('published').default(False)
            table.timestamps()

    def down(self):
        Schema.drop_if_exists('posts')
```

```bash
bazimya migrate
bazimya migrate:rollback --step=2
bazimya migrate:fresh --seed
bazimya migrate:status
```

## Validation

```python
data = self.validate(request, {
    'title': 'required|max:255',
    'email': 'required|email|unique:users,email',
    'age':   'nullable|integer|min:18',
})
```

A failure raises `ValidationException`, which becomes a 422 with the messages
attached. Rules can also live in a form request (`app/Http/Requests`) or a rule
class (`app/Rules`):

```python
class StorePostRequest(FormRequest):
    def authorize(self, request):
        return True

    def rules(self):
        return {'title': 'required|max:255'}


def store(self, request):
    data = StorePostRequest.validate(request)
```

## Extensions

An extension is a package under `extensions/` that brings its own routes,
controllers, commands, middleware, views and migrations. Drop the directory in
and it is live — there is nothing to register.

```bash
bazimya make:extension Blog
```

```python
# extensions/Blog/__init__.py
from bazimya import Extension, Route

extension = Extension('Blog', version='1.0.0', prefix='blog')


class PostController(extension.Controller):
    def index(self, request):
        return self.view('blog::index', posts=[])


@extension.routes
def routes():
    Route.get('/', [PostController, 'index']).name('blog.index')


@extension.command('blog:publish', 'Publish scheduled posts')
def publish(args, options):
    return 'Published.'
```

Its views are addressed as `blog::index` and can extend the application's own
layouts. Override any of them by creating
`resources/views/vendor/blog/index.baz.html`. Its migrations are picked up by
`bazimya migrate`; its commands appear in `bazimya list`.

Application routes are registered before extension routes, so your own route
always wins on a shared URI.

## Deploying

```bash
bazimya build            # VPS: gunicorn + nginx
bazimya build --shared   # shared hosting: cPanel
```

Both produce a `build/` directory that is ready to upload, and a `DEPLOY.md`
inside it with the steps for that target. The build:

- vendors the framework into `vendor/`, so the server needs no `pip`;
- compiles every template ahead of time, so `storage/` can be read-only;
- rewrites `.env` with `APP_ENV=production`, `APP_DEBUG=false` and every
  secret blanked;
- writes `.htaccess` files that keep `app/`, `config/`, `storage/`,
  `database/`, `extensions/` and `vendor/` out of the web root.

**Shared hosting (cPanel).** If the host has **Setup Python App**, point it at
`passenger_wsgi.py` with entry point `application`. If it does not, the app
still runs: `public/index.py` serves it over CGI. Neither needs SSH.

Since shared hosting has no shell, run `bazimya migrate` locally and upload
`database/database.sqlite`, or point it at your MySQL database and migrate
against that.

**VPS.** The build includes `nginx.conf.example` and `bazimya.service.example`.

```bash
gunicorn wsgi:application --workers 3 --bind 127.0.0.1:8000
```

`bazimya doctor` checks an environment and reports what will bite — writable
directories, debug left on in production, a SQLite file inside `public/`, a
missing template cache.

## CLI

```
bazimya new <name>                    Create an application
bazimya serve [--host] [--port]       Development server, with auto-reload
bazimya build [--shared] [--zip]      Build for deployment
bazimya doctor                        Check the environment
bazimya tinker                        REPL with the app booted
bazimya lang [en|rw]                  Show or change the language

bazimya make:controller <Name>        [--resource] [--api] [--model=Post]
bazimya make:model <Name>             [-m] [-c]
bazimya make:migration <name>         [--create=table] [--table=table]
bazimya make:middleware <Name>
bazimya make:request <Name>
bazimya make:rule <Name>
bazimya make:notification <Name>
bazimya make:component <Name>         [--view-only]
bazimya make:provider <Name>
bazimya make:seeder <Name>
bazimya make:command <Name>           [--command=my:name]
bazimya make:extension <Name>         [--prefix=blog]

bazimya migrate                       [--pretend] [--seed]
bazimya migrate:rollback              [--step=1]
bazimya migrate:fresh                 [--seed]
bazimya migrate:status
bazimya db:seed                       [--class=DatabaseSeeder]

bazimya route:list                    [--method] [--path] [--name]
bazimya extension:list                [--commands]
bazimya view:cache
bazimya cache:clear
```

## Authentication, sessions and CSRF

`bazimya new` scaffolds a working login, registration and logout flow —
`app/Http/Controllers/AuthController.py`, `routes/auth.py` and the two views.

```python
from bazimya import Auth, Hash

if Auth.attempt({'email': email, 'password': password}):
    return redirect('/dashboard')
```

Passwords are hashed with scrypt, falling back to pbkdf2 where the host's
OpenSSL lacks it. Sessions are files under `storage/framework/sessions`, with
the id signed by `APP_KEY` so a forged cookie is rejected before anything is
read from disk. `VerifyCsrfToken` is in the `web` group, so `@csrf` in a form
is checked, and a state-changing POST without it gets a 419.

Protect routes with the aliases in `app/Http/Kernel.py`:

```python
Route.middleware('auth').group(lambda: [
    Route.get('/dashboard', [DashboardController, 'index']),
])
```

`storage/framework/sessions` must be **writable** on the server. If it is not,
every request gets a fresh token and every form POST returns 419 — Bazimya
writes a warning to stderr when that happens, and `bazimya doctor` checks it.

## Testing

```python
from tests.TestCase import TestCase


class PostTest(TestCase):
    def test_a_post_can_be_created(self):
        self.acting_as(user)

        response = self.post('/posts', {'title': 'Hello'})

        response.assert_redirect('/posts')
        self.assert_database_has('posts', {'title': 'Hello'})
```

Each test gets a fresh in-memory database with the migrations applied, plus
in-memory sessions, cache and mail — nothing touches your real data. Requests
go straight through the WSGI app, so there is no server to start.

```bash
python -m unittest discover -s tests -p "*Test.py" -t .
pytest                                   # pytest.ini is scaffolded
```

## Also included

`Cache` (file/array), `Storage` (local disks, with path traversal refused),
`Mail` (log/smtp/array via stdlib `smtplib`), `Notification` classes over mail,
database and log channels, an `Event` dispatcher, and `<x-component>` view
components with optional backing classes in `app/View/Components`.

## What is not here yet

Being explicit, so nothing is discovered the hard way:

- **No queue worker.** `config/queue.py` exists but `sync` is the only driver:
  jobs run in the request that dispatched them. Use cron for out-of-band work:
  `* * * * * cd /path/to/app && python bazimya your:command`.
- **No broadcasting.** No websockets, no `routes/channels.py`.
- **No relationships on models.** `has_many` / `belongs_to` are not
  implemented; use the query builder for joins.
- **No authorisation policies or gates.** `AuthServiceProvider` has a
  `policies` dict, but nothing consumes it yet.
- **No password reset or email verification.** The `verified` middleware
  exists and checks an `email_verified_at` column; nothing sends the email.
- **No rate limiting** on login or anywhere else.
- **No asset pipeline.** `resources/css` and `resources/js` are yours to point
  a build at; `public/` is served as-is.

## Licence

MIT.
