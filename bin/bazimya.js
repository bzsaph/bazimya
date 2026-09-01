#!/usr/bin/env node
'use strict';

/*
 * Bazimya's npm entry point.
 *
 *     npx bazimya new blog
 *     npm install -g bazimya && bazimya serve
 *     npm run serve            (inside a generated project)
 *
 * This is a front door, not a second implementation: it finds a Python
 * interpreter and hands the whole argv to the Python kernel, which is the
 * single source of truth for what every command does. Signals and exit codes
 * are forwarded, so Ctrl+C on `bazimya serve` behaves as it would if Python
 * had been invoked directly.
 */

const { spawn } = require('child_process');
const fs = require('fs');
const path = require('path');

const { findPython } = require('../lib/python');

const PACKAGE_ROOT = path.resolve(__dirname, '..');

function fail(message, code) {
  process.stderr.write(`${message}\n`);
  process.exit(code === undefined ? 1 : code);
}

/**
 * Prefer the project's own ./bazimya when we are standing in one.
 *
 * It puts the project root on sys.path and picks up a framework vendored by
 * `bazimya build`, which a globally installed copy would not.
 */
function projectEntry(cwd) {
  let directory = cwd;

  for (;;) {
    const candidate = path.join(directory, 'bazimya');

    if (
      fs.existsSync(candidate) &&
      fs.statSync(candidate).isFile() &&
      fs.existsSync(path.join(directory, 'routes'))
    ) {
      return candidate;
    }

    const parent = path.dirname(directory);

    if (parent === directory) {
      return null;
    }

    directory = parent;
  }
}

function main() {
  const args = process.argv.slice(2);
  const cwd = process.cwd();

  if (!fs.existsSync(path.join(PACKAGE_ROOT, 'bazimya', '__init__.py'))) {
    fail(
      `Bazimya: the Python package is missing from ${PACKAGE_ROOT}.\n` +
        'Reinstall it with "npm install bazimya".'
    );
  }

  let python;

  try {
    python = findPython({ cwd });
  } catch (error) {
    return fail(error.bazimyaHandled ? error.message : `Bazimya: ${error.message}`);
  }

  const entry = projectEntry(cwd);
  const spawnArgs = entry ? [entry, ...args] : ['-m', 'bazimya', ...args];

  const env = Object.assign({}, process.env, {
    // The reloader re-executes this same command; reusing the interpreter we
    // already validated stops it rediscovering a different one.
    BAZIMYA_PYTHON: python.binary,
    BAZIMYA_VIA: 'npm',
  });

  // Outside a project, `python -m bazimya` has to find the package that ships
  // inside this npm install.
  if (!entry) {
    env.PYTHONPATH = env.PYTHONPATH
      ? `${PACKAGE_ROOT}${path.delimiter}${env.PYTHONPATH}`
      : PACKAGE_ROOT;
  }

  const child = spawn(python.binary, spawnArgs, {
    stdio: 'inherit',
    cwd,
    env,
    windowsHide: true,
  });

  // Let the child own the terminal: it prints "Press Ctrl+C to stop", so it
  // should be the one to act on Ctrl+C. Without this Node exits first and
  // leaves the dev server orphaned.
  for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.on(signal, () => {
      if (!child.killed) {
        child.kill(signal);
      }
    });
  }

  child.on('error', (error) => {
    fail(`Bazimya: could not start Python at ${python.binary}.\n${error.message}`);
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      // 128 + signal number is the shell convention; Node gives us only the
      // name, and SIGINT is overwhelmingly the one that matters here.
      process.exit(signal === 'SIGINT' ? 130 : 1);
    }

    process.exit(code === null ? 1 : code);
  });
}

main();
