<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>@yield('title')</title>
    <style>
        :root {
            color-scheme: light dark;
            --bg: #ffffff;
            --fg: #16181d;
            --muted: #6b7280;
            --line: #e5e7eb;
            --accent: #7c5cff;
        }
        @media (prefers-color-scheme: dark) {
            :root {
                --bg: #0f1115;
                --fg: #e8eaed;
                --muted: #9aa0aa;
                --line: #262a33;
            }
        }
        * { box-sizing: border-box; }
        body {
            margin: 0;
            background: var(--bg);
            color: var(--fg);
            font: 16px/1.6 ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
            display: flex;
            flex-direction: column;
            min-height: 100vh;
        }
        main { width: 100%; max-width: 46rem; margin: 0 auto; padding: 4rem 1.5rem; flex: 1; }
        h1 { font-size: clamp(2rem, 6vw, 3rem); margin: 0 0 .25rem; letter-spacing: -.02em; }
        .tag { color: var(--accent); font-weight: 600; font-size: .875rem; text-transform: uppercase; letter-spacing: .08em; }
        ul { list-style: none; padding: 0; margin: 2rem 0 0; }
        li { padding: .85rem 0; border-bottom: 1px solid var(--line); }
        li:first-child { border-top: 1px solid var(--line); }
        code { background: color-mix(in srgb, var(--fg) 8%, transparent); padding: .15em .4em; border-radius: 4px; font-size: .9em; }
        footer { border-top: 1px solid var(--line); padding: 1.5rem; text-align: center; color: var(--muted); font-size: .875rem; }
        a { color: var(--accent); }
    </style>
</head>
<body>
    <main>
        @yield('content')
    </main>

    <footer>
        Bazimya &middot; PHP {{ PHP_VERSION }}
    </footer>
</body>
</html>
