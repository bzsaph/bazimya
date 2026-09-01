"""Builds a directory you can upload and run.

The constraint that shapes all of this is shared hosting with no shell: you
cannot run pip, you cannot run the CLI, and you often cannot move the document
root. So everything that would normally happen on the server happens here —

  - the framework is copied into vendor/, and bootstrap/app.py finds it there;
  - templates are compiled ahead of time, so storage/framework/views can be
    read-only (sessions and logs still need to be writable);
  - .env values are stripped, with APP_DEBUG forced off;
  - .htaccess files are written for routing and to keep app/, config/,
    storage/, database/ and the SQLite file out of the web root.

Two layouts, because hosts differ in one way that matters:

  LAYOUT_VPS      You control nginx and can run a process. gunicorn behind
                  nginx, with the config files to match.
  LAYOUT_SHARED   cPanel. Passenger if the host offers "Setup Python App",
                  CGI through public/index.py if it does not.
"""

import os
import secrets
import shutil
import zipfile

LAYOUT_VPS = "vps"
LAYOUT_SHARED = "shared"

EXCLUDED_DIRECTORIES = {
    ".git",
    ".github",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "tests",
    "build",
    ".venv",
    "venv",
    "env",
}

EXCLUDED_FILES = {
    ".DS_Store",
    ".gitignore",
    "package-lock.json",
    "yarn.lock",
    "Thumbs.db",
}

#: A .env key is blanked in the build when any of these appears in its name.
#: Erring towards blanking: a value wrongly kept is a leak, while one wrongly
#: blanked is a line to fill in.
SECRET_MARKERS = (
    "PASSWORD",
    "SECRET",
    "TOKEN",
    "_KEY",
    "KEY_",
    "APIKEY",
    "CREDENTIAL",
    "USERNAME",
    "_USER",
    "DSN",
    "SECURITY",
    "SALT",
    "SIGNATURE",
    "PRIVATE",
    "SECRET_KEY",
    "AUTH",
)


def _is_secret(key):
    upper = key.upper()

    if upper.endswith("_HOST") or upper in ("DB_DATABASE", "APP_URL"):
        # Hostnames and database names are not credentials, and blanking them
        # makes the upload harder without making it safer.
        return False

    return any(marker in upper for marker in SECRET_MARKERS)


class Bundler:
    def __init__(self, application, target, layout=LAYOUT_VPS, include_env=False):
        if layout not in (LAYOUT_VPS, LAYOUT_SHARED):
            raise ValueError(
                "Unknown layout [{}]. Use '{}' or '{}'.".format(layout, LAYOUT_VPS, LAYOUT_SHARED)
            )

        self.app = application
        self.target = os.path.abspath(target)
        self.layout = layout
        self.include_env = include_env

        self.notes = []
        self.warnings = []
        self.file_count = 0

    # -- build ------------------------------------------------------------

    def build(self):
        self._guard_target()
        self._reset()

        self._copy_application()
        self._vendor_framework()
        self._write_environment()
        self._compile_views()
        self._write_server_config()
        self._protect_private_directories()
        self._prepare_writable_directories()
        self._write_readme()

        return self

    def _guard_target(self):
        """Refuse to build somewhere that would destroy the project.

        Emptying the target is part of the job, so being wrong about what the
        target is would be expensive.
        """
        base = os.path.abspath(self.app.base_path)

        if self.target == base:
            raise RuntimeError("The build target cannot be the project itself.")

        if base.startswith(self.target + os.sep):
            raise RuntimeError(
                "The build target [{}] contains the project. Choose a different --target.".format(
                    self.target
                )
            )

        parent = os.path.dirname(self.target)

        if not os.path.isdir(parent):
            raise RuntimeError("The target's parent directory [{}] does not exist.".format(parent))

    def _reset(self):
        if os.path.isdir(self.target):
            shutil.rmtree(self.target)

        os.makedirs(self.target, exist_ok=True)

    # -- application files ------------------------------------------------

    def _copy_application(self):
        base = os.path.abspath(self.app.base_path)

        for root, directories, files in os.walk(base):
            directories[:] = [d for d in directories if d not in EXCLUDED_DIRECTORIES]

            # Never copy the build into itself.
            if root == self.target or root.startswith(self.target + os.sep):
                directories[:] = []
                continue

            directories[:] = [
                d for d in directories if os.path.join(root, d) != self.target
            ]

            relative_root = os.path.relpath(root, base)
            destination_root = (
                self.target if relative_root == "." else os.path.join(self.target, relative_root)
            )

            os.makedirs(destination_root, exist_ok=True)

            for name in files:
                relative = os.path.normpath(
                    name if relative_root == "." else os.path.join(relative_root, name)
                )

                if self._excluded(relative, name):
                    continue

                shutil.copy2(os.path.join(root, name), os.path.join(destination_root, name))
                self.file_count += 1

    def _excluded(self, relative, name):
        if name in EXCLUDED_FILES or name.endswith((".pyc", ".pyo")):
            return True

        # .env carries production secrets. It is rewritten separately, and
        # only copied verbatim when explicitly asked for.
        if relative == ".env" and not self.include_env:
            return True

        # Logs and compiled views are rebuilt; a local SQLite database is
        # almost never what should go to the server.
        for prefix in ("storage" + os.sep + "logs", "storage" + os.sep + "framework"):
            if relative.startswith(prefix) and name != ".gitkeep":
                return True

        if name.endswith(".sqlite") or name.endswith(".sqlite3"):
            self.warnings.append(
                "Left {} out of the build. Upload it by hand if the server "
                "really should start with your local data.".format(relative)
            )

            return True

        return False

    # -- the framework ----------------------------------------------------

    def _vendor_framework(self):
        """Copy Bazimya into vendor/ so the server needs no pip.

        bootstrap/app.py adds vendor/ to sys.path only when bazimya is not
        already importable, so a host that does have it installed keeps using
        its own copy.
        """
        source = self.app.framework_path()
        destination = os.path.join(self.target, "vendor", "bazimya")

        shutil.copytree(
            source,
            destination,
            ignore=shutil.ignore_patterns(
                "__pycache__", "*.pyc", "*.pyo", ".git", "tests", "node_modules"
            ),
        )

        for root, _, files in os.walk(destination):
            self.file_count += len(files)

        self.notes.append("Vendored the framework into vendor/ — the server needs no pip.")

    # -- environment ------------------------------------------------------

    def _write_environment(self):
        target = os.path.join(self.target, ".env")

        if self.include_env and os.path.isfile(target):
            self.warnings.append(
                "This build contains your real .env, secrets included. Do not commit or share it."
            )

            return

        source = self.app.path(".env")
        lines = []

        if os.path.isfile(source):
            with open(source, "r", encoding="utf-8") as handle:
                for line in handle.read().splitlines():
                    stripped = line.strip()

                    if not stripped or stripped.startswith("#") or "=" not in stripped:
                        lines.append(line)
                        continue

                    key = stripped.split("=", 1)[0].strip()

                    # Secrets are blanked; everything else is carried over.
                    # Blanking DB_CONNECTION or APP_NAME would only make the
                    # upload harder to finish, and neither is sensitive.
                    if key == "APP_ENV":
                        lines.append("APP_ENV=production")
                    elif key == "APP_DEBUG":
                        lines.append("APP_DEBUG=false")
                    elif key == "APP_KEY":
                        lines.append("APP_KEY=" + secrets.token_hex(16))
                    elif _is_secret(key):
                        lines.append(key + "=")
                    else:
                        lines.append(line)

        if not lines:
            lines = [
                "APP_ENV=production",
                "APP_DEBUG=false",
                "APP_KEY=" + secrets.token_hex(16),
                "DB_CONNECTION=sqlite",
                "DB_DATABASE=database/database.sqlite",
            ]

        contents = "\n".join(lines) + "\n"

        for name in (".env", ".env.example"):
            with open(os.path.join(self.target, name), "w", encoding="utf-8") as handle:
                handle.write(contents)

            self.file_count += 1

        self.notes.append(
            "Wrote .env with APP_ENV=production and APP_DEBUG=false; other values are blank."
        )

    # -- views ------------------------------------------------------------

    def _compile_views(self):
        """Compile every template into the build.

        This is what lets storage/ be read-only on the server, and it removes
        the compile cost from the first request to every page.
        """
        from ..view.view import EXTENSION, View

        source_views = self.app.views_path()
        cache = os.path.join(self.target, "storage", "framework", "views")
        os.makedirs(cache, exist_ok=True)

        # Compile against the *source* paths, because that is what the cache
        # keys are derived from at runtime — and the deployed app will resolve
        # templates from its own tree.
        deployed_views = os.path.join(self.target, "resources", "views")
        view = View(deployed_views, cache, root=self.target)

        directories = [deployed_views]

        try:
            self.app.boot()

            for extension in self.app.make("extensions").all():
                path = extension.migrations_path()  # touch, to surface failures early
                views = extension.views_path()

                if views:
                    # Point at the copy inside the build, not the original.
                    relative = os.path.relpath(views, self.app.base_path)
                    directories.append(os.path.join(self.target, relative))
        except Exception:  # noqa: BLE001 — a broken extension is reported by
            # `extension:list`; it must not stop a build of the rest.
            pass

        compiled = 0
        failed = []

        for directory in directories:
            if not os.path.isdir(directory):
                continue

            for root, _, files in os.walk(directory):
                for name in files:
                    if not name.endswith(EXTENSION):
                        continue

                    path = os.path.join(root, name)

                    try:
                        source = view._compile(path, os.path.relpath(path, directory))
                        view._write_cache(view._cache_file(path), source)
                        compiled += 1
                    except Exception as error:  # noqa: BLE001
                        failed.append((path, str(error)))

        for path, message in failed:
            self.warnings.append("Template {} failed to compile: {}".format(path, message))

        if compiled:
            self.notes.append("Compiled {} template(s) ahead of time.".format(compiled))

        self.file_count += compiled

    # -- web server configuration -----------------------------------------

    def _write_server_config(self):
        if self.layout == LAYOUT_SHARED:
            self._write(".htaccess", self._shared_htaccess())
            self._write("public/.htaccess", self._public_htaccess())
            self.notes.append(
                "Wrote .htaccess for cPanel: Passenger if the host has it, CGI if not."
            )
        else:
            self._write("nginx.conf.example", self._nginx_config())
            self._write("bazimya.service.example", self._systemd_unit())
            self._write("public/.htaccess", self._public_htaccess())
            self.notes.append("Wrote nginx and systemd examples for a VPS.")

    def _write(self, relative, contents):
        path = os.path.join(self.target, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w", encoding="utf-8") as handle:
            handle.write(contents)

        self.file_count += 1

    def _shared_htaccess(self):
        return """# Bazimya — shared hosting.
#
# Upload this whole folder into public_html (or set the domain's document root
# to it). Two paths are covered:
#
#   1. The host offers "Setup Python App" (Passenger). Configure it there and
#      Passenger intercepts before any of this file applies.
#   2. It does not. Requests fall through to public/index.py over CGI.

<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /

    # Nothing outside public/ is ever served.
    RewriteRule ^(app|bootstrap|config|database|extensions|resources|routes|storage|tests|vendor)(/|$) - [F,L]
    RewriteRule ^(\\.env|\\.env\\..*|passenger_wsgi\\.py|wsgi\\.py|bazimya|requirements\\.txt|package\\.json)$ - [F,L]

    # A real file inside public/ is served as-is.
    RewriteCond %{DOCUMENT_ROOT}/public%{REQUEST_URI} -f
    RewriteRule ^(.*)$ public/$1 [L]

    # Everything else goes to the front controller.
    RewriteRule ^(.*)$ public/index.py/$1 [L,QSA]
</IfModule>

<IfModule mod_headers.c>
    Header set X-Content-Type-Options "nosniff"
    Header set X-Frame-Options "SAMEORIGIN"
    Header set Referrer-Policy "strict-origin-when-cross-origin"
</IfModule>

Options -Indexes
"""

    def _public_htaccess(self):
        return """# Bazimya — rules for when the document root points at public/.

<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /

    RewriteCond %{REQUEST_FILENAME} -f [OR]
    RewriteCond %{REQUEST_FILENAME} -d
    RewriteRule ^ - [L]

    RewriteRule ^(.*)$ index.py/$1 [L,QSA]
</IfModule>

# Some CGI setups drop the Authorization header, which is why bearer tokens
# "work locally but not on the host".
<IfModule mod_rewrite.c>
    RewriteCond %{HTTP:Authorization} .
    RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
</IfModule>

<IfModule mod_headers.c>
    Header set X-Content-Type-Options "nosniff"
    Header set X-Frame-Options "SAMEORIGIN"
</IfModule>

AddHandler cgi-script .py
Options +ExecCGI -Indexes
"""

    def _nginx_config(self):
        return """# Bazimya on nginx, in front of gunicorn.
#
#   ln -s ../sites-available/your-site /etc/nginx/sites-enabled/
#   nginx -t && systemctl reload nginx

upstream bazimya {
    server 127.0.0.1:8000 fail_timeout=0;
}

server {
    listen 80;
    server_name example.com;

    # Static files are served by nginx; everything else goes to the app.
    root /var/www/your-app/public;

    client_max_body_size 32m;

    location / {
        try_files $uri @app;
    }

    location @app {
        proxy_pass http://bazimya;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

        # Without this the app cannot tell HTTPS from HTTP behind the proxy,
        # and every generated URL comes out as http://.
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_redirect off;
        proxy_read_timeout 120s;
    }

    location ~ /\\.(?!well-known).* {
        deny all;
    }
}
"""

    def _systemd_unit(self):
        return """# /etc/systemd/system/bazimya.service
#
#   systemctl daemon-reload
#   systemctl enable --now bazimya

[Unit]
Description=Bazimya application
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/var/www/your-app
Environment="PATH=/var/www/your-app/.venv/bin"

ExecStart=/var/www/your-app/.venv/bin/gunicorn wsgi:application \\
    --workers 3 \\
    --bind 127.0.0.1:8000 \\
    --timeout 120 \\
    --access-logfile - \\
    --error-logfile -

ExecReload=/bin/kill -s HUP $MAINPID
Restart=always
RestartSec=3

# The app only ever writes to storage/ and database/.
ProtectSystem=full
PrivateTmp=true
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""

    def _protect_private_directories(self):
        """Deny-all rules in every directory that must not be served.

        The front .htaccess covers this already, but a host with mod_rewrite
        disabled would ignore it — and a SQLite database one URL away is not
        worth betting on a single line of config.
        """
        deny = """# Bazimya — nothing here should ever be served over HTTP.

<IfModule mod_authz_core.c>
    Require all denied
</IfModule>
<IfModule !mod_authz_core.c>
    Order deny,allow
    Deny from all
</IfModule>
"""

        for directory in (
            "app",
            "bootstrap",
            "config",
            "database",
            "extensions",
            "resources",
            "routes",
            "storage",
            "vendor",
        ):
            path = os.path.join(self.target, directory)

            if os.path.isdir(path):
                self._write(os.path.join(directory, ".htaccess"), deny)

    def _prepare_writable_directories(self):
        for directory in (
            "storage/framework/views",
            "storage/framework/cache",
            "storage/logs",
            "database",
        ):
            path = os.path.join(self.target, directory)
            os.makedirs(path, exist_ok=True)

            keep = os.path.join(path, ".gitkeep")

            if not os.path.isfile(keep):
                open(keep, "w", encoding="utf-8").close()

        self.notes.append(
            "storage/ and database/ must be writable by the web server (0755, or 0775 "
            "if it runs as a different user)."
        )

    # -- instructions -----------------------------------------------------

    def _write_readme(self):
        writer = self._shared_readme if self.layout == LAYOUT_SHARED else self._vps_readme

        self._write("DEPLOY.md", writer())

    def _shared_readme(self):
        return """# Deploying to shared hosting

Built for **cPanel-style shared hosting**. Nothing here needs pip, npm or SSH:
the framework travels with the app in `vendor/`, and every template is already
compiled.

## 1. Upload

Upload everything in this folder. Either:

- **Set the domain's document root to this folder.** The included `.htaccess`
  routes requests into `public/` and blocks direct access to `app/`, `config/`,
  `storage/`, `database/`, `extensions/` and `vendor/`; or
- upload it into `public_html/` directly, which does the same thing.

## 2. Set up Python

Look for **Setup Python App** in cPanel. If it is there:

| Field | Value |
| --- | --- |
| Python version | 3.8 or newer |
| Application root | this folder |
| Application URL | your domain |
| Application startup file | `passenger_wsgi.py` |
| Application entry point | `application` |

Create it, then press **Restart**. That is the fast path — the app stays
running between requests.

**If there is no such option**, the app still works: `public/index.py` runs it
over CGI, which starts a fresh interpreter per request. Slower, but it needs
nothing configured. Make sure `public/index.py` is executable (0755).

## 3. Fill in .env

Edit `.env`. It was written with `APP_ENV=production` and `APP_DEBUG=false`,
and every other value blanked. Fill in your database credentials.

Leave `APP_DEBUG=false`. With it on, a stack trace containing your credentials
is one error away from being public.

## 4. Make these directories writable

    storage/framework/sessions/   required — logins and CSRF depend on it
    storage/framework/cache/      required if you use the cache
    storage/logs/                 required, or errors go unrecorded
    database/                     only if you are using SQLite

    chmod -R 775 storage database

`storage/framework/views/` is the exception: templates were compiled into this
build, so it can stay read-only.

If sessions cannot be written, every request gets a new CSRF token and every
form POST fails with **419 Page Expired**. That is the symptom to look for.

## 5. Create the tables

Shared hosting has no shell, so `bazimya migrate` cannot be run there. Two
options:

- **SQLite**: run `bazimya migrate` locally, then upload
  `database/database.sqlite`. Simplest, and it is why SQLite is the default.
- **MySQL**: create the database in cPanel, then run the migrations locally
  against it with the same credentials, or import a `.sql` dump through
  phpMyAdmin.

## 6. Check it

Open the site. On a 500, temporarily set `APP_DEBUG=true`, reload, read the
message, then set it back to `false`. `storage/logs/bazimya.log` also has it.

## Updating

Run `bazimya build --shared` again and re-upload. Keep the server's `.env` —
the build does not overwrite it unless you pass `--with-env`.
"""

    def _vps_readme(self):
        return """# Deploying to a VPS

Built for **nginx in front of gunicorn**. The framework is vendored into
`vendor/`, so a virtualenv is optional — but use one anyway if you have
dependencies of your own.

## 1. Upload

    rsync -av --delete ./ user@server:/var/www/your-app/

## 2. Install

    cd /var/www/your-app
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt   # if you have any
    .venv/bin/pip install gunicorn

## 3. Fill in .env

`.env` was written with `APP_ENV=production` and `APP_DEBUG=false`, and every
other value blanked. Fill in your database credentials, and leave debug off.

## 4. Migrate

    .venv/bin/python bazimya migrate

## 5. Run it

`bazimya.service.example` is a systemd unit; `nginx.conf.example` is the site
config. Adjust the paths in both, then:

    cp bazimya.service.example /etc/systemd/system/bazimya.service
    systemctl daemon-reload && systemctl enable --now bazimya

    cp nginx.conf.example /etc/nginx/sites-available/your-app
    ln -s ../sites-available/your-app /etc/nginx/sites-enabled/
    nginx -t && systemctl reload nginx

Point nginx's `root` at this folder's `public/` so nginx serves static files
directly and only application requests reach gunicorn.

## 6. Permissions

    chown -R www-data:www-data storage database
    chmod -R 775 storage database

`storage/framework/sessions` must be writable or logins and CSRF will not
work — the symptom is every form POST returning 419.

## 7. HTTPS

    certbot --nginx -d example.com

`X-Forwarded-Proto` is already set in the nginx example, which is what lets the
app generate `https://` URLs behind the proxy.

## Updating

Re-run `bazimya build`, rsync again, then:

    .venv/bin/python bazimya migrate
    systemctl restart bazimya
"""

    # -- zipping ----------------------------------------------------------

    def zip(self, archive=None):
        archive = archive or self.target + ".zip"

        if os.path.isfile(archive):
            os.remove(archive)

        with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
            for root, _, files in os.walk(self.target):
                for name in files:
                    path = os.path.join(root, name)
                    bundle.write(path, os.path.relpath(path, self.target))

        return archive
