# -*- coding: utf-8 -*-
"""Ikinyarwanda — the Kinyarwanda catalogue.

Keyed by the English sentence. Anything missing here falls back to English,
so a partial catalogue is safe to ship.

House style, so the framework sounds like one voice:

  * Speak to the person directly: "Tanga izina", not "Izina rigomba gutangwa".
  * Keep the words that name a file or a folder in English — a beginner has
    to type app/Models and see `migrate` on their screen, so translating
    those would make the instruction impossible to follow.
  * Loanwords already used by Rwandan developers (seriveri, dosiye, porogaramu)
    beat invented pure-Kinyarwanda terms nobody would recognise.
"""

MESSAGES = {
    # -- the framework itself ---------------------------------------------
    "A Python web framework with no dependencies.":
        "Urwego rwo kubaka imbuga rwa Python rutagira ikindi rusaba.",
    "USAGE": "UKO RIKORESHWA",
    "COMMANDS": "AMATEGEKO",

    # -- new ---------------------------------------------------------------
    "Create a new Bazimya application": "Rema porogaramu nshya ya Bazimya",
    "Please give the application a name.": "Nyamuneka tanga izina rya porogaramu.",
    "Directory [{}] already exists and is not empty.":
        "Ububiko [{}] busanzwe buhari kandi burimo ibintu.",
    "Use --force to write into it anyway.":
        "Koresha --force niba ushaka kwandikamo uko byaba bimeze kose.",
    "The application skeleton is missing at":
        "Urwego rw'ibanze rwa porogaramu ntirubonetse muri",
    "Creating a Bazimya application in {}":
        "Kurema porogaramu ya Bazimya muri {}",
    "Scaffolded {} files.": "Hakozwe dosiye {}.",
    "Next:": "Ibikurikira:",
    "Then open http://127.0.0.1:8000": "Hanyuma ufungure http://127.0.0.1:8000",
    "Deploying:": "Kohereza kuri seriveri:",

    # -- serve -------------------------------------------------------------
    "Run the development server": "Tangiza seriveri yo kwigeragereza",
    "Bazimya development server": "Seriveri ya Bazimya yo kwigeragereza",
    "Network:   listening on every interface":
        "Urusobe:   yumva kuri buri muyoboro",
    "Press Ctrl+C to stop.": "Kanda Ctrl+C kugira ngo uhagarike.",

    # -- build -------------------------------------------------------------
    "Build an upload-ready copy of the app for a server":
        "Tegura kopi ya porogaramu yiteguye koherezwa kuri seriveri",
    "Building for": "Turimo gutegura kuri",
    "Build complete — {} files.": "Gutegura byarangiye — dosiye {}.",
    "Read": "Soma",
    "/DEPLOY.md before uploading.": "/DEPLOY.md mbere yo kohereza.",

    # -- migrate -----------------------------------------------------------
    "Run the pending database migrations":
        "Koresha za migration zitegereje",
    "Roll back the last batch of migrations":
        "Subiza inyuma itsinda rya nyuma rya za migration",
    "Roll everything back and migrate again":
        "Subiza byose inyuma hanyuma wongere ukore za migration",
    "Show which migrations have run":
        "Erekana za migration zamaze gukorwa",
    "Run the database seeders":
        "Koresha za seeder zuzuza ububiko bw'amakuru",
    "Nothing to migrate.": "Nta migration isigaye.",
    "Nothing to roll back.": "Nta cyo gusubiza inyuma.",
    "No migrations found.": "Nta migration yabonetse.",
    "Everything is migrated.": "Za migration zose zarangiye.",
    "Migrated {} migration{}.": "Hakozwe za migration {}.",
    "Rolled back {} migration{}.": "Hasubijwe inyuma za migration {}.",
    "Rolling everything back...": "Gusubiza byose inyuma...",
    "Database refreshed.": "Ububiko bw'amakuru bwavuguruwe.",
    "Seeding:": "Kuzuza amakuru:",
    "Seeding complete.": "Kuzuza amakuru byarangiye.",
    "Seeder [{}] was not found at {}": "Seeder [{}] ntiyabonetse muri {}",
    "--pretend: nothing was actually run.":
        "--pretend: nta cyakozwe by'ukuri.",
    "APP_ENV is production. migrate:fresh will drop every table.":
        "APP_ENV ni production. migrate:fresh izasiba imbonerahamwe zose.",
    "Really do this?": "Ubyemeje koko?",
    "Cancelled.": "Byahagaritswe.",
    "running": "irimo gukora",
    "rolled back": "yasubijwe inyuma",
    "migrated": "yarakozwe",
    "{} pending. Run: bazimya migrate":
        "{} zitegereje. Koresha: bazimya migrate",

    # -- make --------------------------------------------------------------
    "Create a controller in app/Http/Controllers":
        "Rema controller muri app/Http/Controllers",
    "Create a model in app/Models": "Rema model muri app/Models",
    "Create a migration in database/migrations":
        "Rema migration muri database/migrations",
    "Create middleware in app/Http/Middleware":
        "Rema middleware muri app/Http/Middleware",
    "Create a service provider in app/Providers":
        "Rema service provider muri app/Providers",
    "Create a seeder in database/seeders":
        "Rema seeder muri database/seeders",
    "Scaffold an extension in extensions/":
        "Rema umugereka muri extensions/",
    "Create a form request in app/Http/Requests":
        "Rema form request muri app/Http/Requests",
    "Create a validation rule in app/Rules":
        "Rema itegeko ryo kugenzura muri app/Rules",
    "Create a console command in app/Console/Commands":
        "Rema itegeko rya console muri app/Console/Commands",
    "Create a notification in app/Notifications":
        "Rema notification muri app/Notifications",
    "Create a view component and its template":
        "Rema igice cy'urupapuro n'inyandiko yacyo",
    "Please give it a name.": "Nyamuneka tanga izina.",
    "Please give the component a name.": "Nyamuneka tanga izina ry'igice.",
    "Please give the extension a name.": "Nyamuneka tanga izina ry'umugereka.",
    "Please name the migration, e.g. create_posts_table.":
        "Nyamuneka tanga izina rya migration, urugero create_posts_table.",
    "Created": "Byaremwe",
    "Already exists:": "Bisanzwe bihari:",
    "Use --force to overwrite it.": "Koresha --force kugira ngo ubisimbure.",
    "Extension [{}] already exists.": "Umugereka [{}] usanzwe uhari.",
    "Extension [{}] created.": "Umugereka [{}] waremwe.",
    "Component <x-{}> created.": "Igice <x-{}> cyaremwe.",
    "Use it in a template:": "Gikoreshe muri template:",
    "Register it in app/Http/Kernel.py:": "Yandike muri app/Http/Kernel.py:",
    "Add it to app/Console/Kernel.py:": "Yongere muri app/Console/Kernel.py:",
    "Add it to the providers list in config/app.py:":
        "Yongere ku rutonde rwa providers muri config/app.py:",
    "Create one with:": "Rema imwe ukoresheje:",
    "Create one with:  bazimya make:seeder":
        "Rema imwe ukoresheje:  bazimya make:seeder",
    "{} does not define a class called {}.":
        "{} ntabwo irimo class yitwa {}.",

    # -- inspect -----------------------------------------------------------
    "List the registered routes": "Erekana inzira zanditswe",
    "List the installed extensions": "Erekana imigereka yashyizwemo",
    "Clear the compiled templates": "Siba za template zateguwe",
    "Compile every template ahead of time":
        "Tegura za template zose mbere y'igihe",
    "Open a Python REPL with the application booted":
        "Fungura Python REPL porogaramu imaze gutangira",
    "No extensions installed.": "Nta mugereka washyizwemo.",
    "No extension commands.": "Nta mategeko y'imigereka ahari.",
    "Cleared {} compiled template{}.": "Hasibwe za template {}.",
    "Compiled {} template{}.": "Hateguwe za template {}.",
    "{} route{}.": "Inzira {}.",
    "{} template(s) failed to compile:": "Za template {} zanze gutegurwa:",
    "{} extension(s) failed to load:": "Imigereka {} yanze gutangira:",
    "could not load:": "ntibyashoboye gutangira:",
    "Do this before deploying — it removes the first-hit compile cost":
        "Bikore mbere yo kohereza — bikuraho gutegereza kw'ubwa mbere",
    "and works on hosts where storage/ is read-only.":
        "kandi bikora kuri seriveri aho storage/ idashobora kwandikwaho.",

    # -- doctor ------------------------------------------------------------
    "Check the environment for anything that will bite in production":
        "Suzuma niba nta kibazo kizavuka igihe porogaramu izaba ikora",
    "Bazimya {} — environment check": "Bazimya {} — isuzuma ry'aho ikorera",
    "Everything checks out.": "Byose bimeze neza.",
    "Not inside a Bazimya project; project checks skipped.":
        "Ntabwo turi mu mushinga wa Bazimya; isuzuma ry'umushinga ryasimbutswe.",
    "{} problem(s) to fix.": "Hari ibibazo {} bigomba gukosorwa.",
    "{} thing(s) worth knowing about.": "Hari ibintu {} byiza kumenya.",
    "Set APP_KEY in .env.": "Shyiraho APP_KEY muri .env.",
    "Set APP_DEBUG=false. Stack traces leak credentials.":
        "Shyiraho APP_DEBUG=false. Amakosa arambuye atuma amabanga amenyekana.",
    "Set SESSION_SECURE_COOKIE=true once the site is on HTTPS.":
        "Shyiraho SESSION_SECURE_COOKIE=true igihe urubuga rugeze kuri HTTPS.",
    "the SQLite file is inside public/": "dosiye ya SQLite iri muri public/",
    "Move it to database/ — it is downloadable where it is.":
        "Yimurire muri database/ — aho iri, umuntu wese arashobora kuyimanura.",
    "The default database driver needs it.":
        "Ububiko bw'amakuru busanzwe burabikeneye.",
    "scrypt is not in this OpenSSL build;":
        "scrypt ntiboneka muri iyi OpenSSL;",
    "using pbkdf2 instead, which is still sound.":
        "hakoreshejwe pbkdf2, na yo ifite umutekano.",
    "Run `bazimya view:cache` before deploying to a":
        "Koresha `bazimya view:cache` mbere yo kohereza kuri",
    "host where storage/ is read-only.":
        "seriveri aho storage/ idashobora kwandikwaho.",
    "the application failed to boot:": "porogaramu yanze gutangira:",
    "reachable": "iraboneka",
    "unreachable": "ntiboneka",
    "missing": "ntibonetse",
    "not set": "ntabwo yashyizweho",
    "ON in production": "IRAKORA muri production",
    "off in production": "izimye muri production",

    # -- the kernel: errors and help --------------------------------------
    'Unknown command "{}".': 'Itegeko "{}" ntirizwi.',
    "Did you mean:": "Wenda washakaga:",
    'Run "bazimya list" to see every command.':
        'Andika "bazimya list" urebe amategeko yose.',
    "This does not look like a Bazimya project.":
        "Aha ntihasa n'umushinga wa Bazimya.",
    "Run this from a project directory, or create one:":
        "Ibi bikorerwa mu bubiko bw'umushinga; cyangwa urema umushinga mushya:",
    "Run again with BAZIMYA_DEBUG=1 for the traceback.":
        "Ongera ukoreshe BAZIMYA_DEBUG=1 kugira ngo urebe aho ikosa rituruka.",
    "This command must be run from inside a Bazimya project.\n"
    "Create one with:  bazimya new my-app":
        "Iri tegeko rikorerwa mu mushinga wa Bazimya.\n"
        "Rema umushinga ukoresheje:  bazimya new my-app",
    "Stub [{}] was not found at {}": "Stub [{}] ntiyabonetse muri {}",
    "{} must implement handle().": "{} igomba kugira handle().",

    # -- doctor: headings, labels and values ------------------------------
    "Project": "Umushinga",
    "Python": "Python",
    "Boot": "Gutangira",
    "Configuration": "Igenamiterere",
    "Database": "Ububiko bw'amakuru",
    "Security": "Umutekano",
    "Extensions": "Imigereka",
    "Deployment": "Kohereza kuri seriveri",
    "Writable directories": "Ububiko bwandikwamo",
    "binary": "porogaramu",
    "version": "verisiyo",
    "platform": "sisitemu",
    "env": "aho ikorera",
    "debug": "debug",
    "driver": "ubwoko",
    "password hash": "ihishwa ry'ijambobanga",
    "sessions": "sessions",
    "cookie secure": "cookie ifite umutekano",
    "compiled views": "amapaji yateguwe",
    "found": "byabonetse",
    "available": "birahari",
    "none": "nta na kimwe",
    "on": "birakora",
    "off": "ntibikora",

    # -- migrate: the per-migration lines ---------------------------------
    "running   {}": "irimo gukora   {}",
    "rolled back   {}": "yasubijwe inyuma   {}",

    # -- table headings ----------------------------------------------------
    "Ran": "Byakozwe",
    "Migration": "Migration",
    "Path": "Inzira",
    "Method": "Uburyo",
    "URI": "URI",
    "Name": "Izina",
    "Action": "Igikorwa",
    "Middleware": "Middleware",
    "Extension": "Umugereka",
    "Version": "Verisiyo",
    "Prefix": "Imbanziriza",
    "Commands": "Amategeko",
    "Description": "Ibisobanuro",
    "Command": "Itegeko",
    "Yes": "Yego",
    "No": "Oya",

    "connection": "ihuza",
    "writable": "birandikwaho",
    "NOT writable": "NTIBIRANDIKWAHO",

    # -- validation: what a visitor to the site reads ---------------------
    "The {field} field is required.": "Umwanya {field} ugomba kuzuzwa.",
    "The {field} field must be a valid email address.":
        "{field} igomba kuba imeyili nyayo.",
    "The {field} field must be a valid URL.": "{field} igomba kuba URL nyayo.",
    "The {field} field must be a whole number.":
        "{field} igomba kuba umubare wuzuye.",
    "The {field} field must be a number.": "{field} igomba kuba umubare.",
    "The {field} field must be true or false.":
        "{field} igomba kuba true cyangwa false.",
    "The {field} field may only contain letters.":
        "{field} igomba kuba irimo inyuguti gusa.",
    "The {field} field may only contain letters and numbers.":
        "{field} igomba kuba irimo inyuguti n'imibare gusa.",
    "The {field} field may only contain letters, numbers, dashes and underscores.":
        "{field} igomba kuba irimo inyuguti, imibare, udukoni n'udukoni two hasi gusa.",
    "The {field} field must be a valid slug.": "{field} igomba kuba slug nyayo.",
    "The {field} field must be a valid UUID.": "{field} igomba kuba UUID nyayo.",
    "The {field} field must be at least {parameter}.":
        "{field} igomba kuba nibura {parameter}.",
    "The {field} field may not be greater than {parameter}.":
        "{field} ntigomba kurenga {parameter}.",
    "The {field} field must be between {parameter}.":
        "{field} igomba kuba hagati ya {parameter}.",
    "The {field} field must be exactly {parameter}.":
        "{field} igomba kuba {parameter} neza.",
    "The selected {field} is invalid.": "{field} watoranyije ntabwo yemewe.",
    "The {field} confirmation does not match.":
        "Kwemeza {field} ntibihuye.",
    "The {field} and {parameter} fields must match.":
        "{field} na {parameter} bigomba guhura.",
    "The {field} and {parameter} fields must be different.":
        "{field} na {parameter} bigomba gutandukana.",
    "The {field} field format is invalid.": "Imiterere ya {field} ntiyemewe.",
    "The {field} field must be a valid date.":
        "{field} igomba kuba itariki nyayo.",
    "The {field} has already been taken.": "{field} isanzwe ikoreshwa.",
    "The {field} field must be accepted.": "{field} igomba kwemerwa.",
    "The {field} field is invalid.": "{field} ntiyemewe.",

    # -- the lang command --------------------------------------------------
    "Show or change the language Bazimya speaks":
        "Erekana cyangwa uhindure ururimi Bazimya ivuga",
    "Language": "Ururimi",
    "Change it with:  bazimya lang rw": "Uhindure ukoresheje:  bazimya lang en",
    "Unsupported language: {}": "Ururimi ntirwemewe: {}",
    "Available:": "Indimi zihari:",
    "Not inside a project, so there is no .env to change.":
        "Ntabwo turi mu mushinga, nta .env yo guhindura.",
    "Use it for a single command:": "Rukoreshe ku itegeko rimwe gusa:",
    "No .env file at": "Nta dosiye .env iri muri",
    "Language set to {} ({}).": "Ururimi rwahinduwe ruba {} ({}).",
    "Everything Bazimya says will now be in {}.":
        "Ubu Bazimya izajya ivuga mu {}.",
}
