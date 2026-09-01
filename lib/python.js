'use strict';

/*
 * Locating a usable Python interpreter.
 *
 * The Node CLI is a front door, not a runtime — every command ends up in the
 * Python kernel. Finding Python is therefore the one job that has to be
 * reliable on machines we cannot inspect, so we look in this order:
 *
 *   1. BAZIMYA_PYTHON             — explicit override, always wins
 *   2. A project virtualenv       — .venv/ or venv/ next to the project
 *   3. "python" in package.json   — per-project pin
 *   4. PATH                       — the normal case
 *   5. Well-known locations       — Homebrew, python.org, cPanel/CloudLinux
 *
 * Anything found is version-checked before use: a Python 2.7 still called
 * `python` on the PATH is a real situation, and failing with a SyntaxError
 * from inside the framework helps nobody.
 */

const { spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const MINIMUM_PYTHON = [3, 8];

/** A virtualenv beside the project is almost always the right interpreter. */
function virtualenvCandidates(cwd) {
  const candidates = [];
  const binary = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python3';
  const fallback = process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python';

  let directory = cwd;

  for (;;) {
    for (const name of ['.venv', 'venv', 'env']) {
      candidates.push(path.join(directory, name, binary));
      candidates.push(path.join(directory, name, fallback));
    }

    // Stop at the project root rather than walking to /.
    if (fs.existsSync(path.join(directory, 'bazimya')) || fs.existsSync(path.join(directory, 'routes'))) {
      break;
    }

    const parent = path.dirname(directory);

    if (parent === directory) {
      break;
    }

    directory = parent;
  }

  return candidates.filter((candidate) => fs.existsSync(candidate));
}

function candidatePaths() {
  if (process.platform === 'win32') {
    const candidates = ['python.exe', 'python3.exe', 'py.exe'];

    for (const version of ['313', '312', '311', '310', '39', '38']) {
      candidates.push(`C:\\Python${version}\\python.exe`);
      candidates.push(
        path.join(os.homedir(), `AppData\\Local\\Programs\\Python\\Python${version}\\python.exe`)
      );
    }

    return candidates;
  }

  const candidates = ['python3', 'python'];

  for (const version of ['3.13', '3.12', '3.11', '3.10', '3.9', '3.8']) {
    candidates.push(`python${version}`);
    candidates.push(`/usr/local/bin/python${version}`);
    candidates.push(`/usr/bin/python${version}`);
    candidates.push(`/opt/homebrew/bin/python${version}`);
    candidates.push(`/Library/Frameworks/Python.framework/Versions/${version}/bin/python3`);
  }

  // CloudLinux / cPanel install alternative Pythons out of the way.
  for (const version of ['312', '311', '310', '39', '38']) {
    candidates.push(`/opt/alt/python${version}/bin/python3`);
  }

  candidates.push('/usr/local/bin/python3', '/usr/bin/python3', '/opt/homebrew/bin/python3');

  return candidates;
}

/** Ask a binary for its version. Null when it is not usable Python. */
function inspect(binary) {
  let result;

  try {
    result = spawnSync(binary, ['-c', 'import sys; print("%d.%d.%d" % sys.version_info[:3])'], {
      encoding: 'utf8',
      timeout: 10000,
      windowsHide: true,
    });
  } catch (error) {
    return null;
  }

  if (!result || result.error || result.status !== 0) {
    return null;
  }

  const raw = String(result.stdout || '').trim();
  const match = raw.match(/^(\d+)\.(\d+)\.(\d+)/);

  if (!match) {
    return null;
  }

  const major = Number(match[1]);
  const minor = Number(match[2]);
  const supported =
    major > MINIMUM_PYTHON[0] ||
    (major === MINIMUM_PYTHON[0] && minor >= MINIMUM_PYTHON[1]);

  return { binary, version: raw, major, minor, supported };
}

/** Read a "python" pin out of the nearest package.json, walking upwards. */
function pinnedInPackageJson(startDirectory) {
  let directory = startDirectory || process.cwd();

  for (;;) {
    const manifest = path.join(directory, 'package.json');

    if (fs.existsSync(manifest)) {
      try {
        const parsed = JSON.parse(fs.readFileSync(manifest, 'utf8'));
        const pin = parsed && parsed.bazimya && parsed.bazimya.python;

        if (typeof pin === 'string' && pin.trim() !== '') {
          return pin.trim();
        }
      } catch (error) {
        // A malformed package.json is the user's problem to fix, not a reason
        // to abort the search.
      }
    }

    const parent = path.dirname(directory);

    if (parent === directory) {
      return null;
    }

    directory = parent;
  }
}

function findPython(options) {
  const settings = options || {};
  const cwd = settings.cwd || process.cwd();
  const tooOld = [];
  const tried = new Set();

  // An explicit choice is an instruction, not a suggestion: if it does not
  // work, say so rather than quietly using something else.
  const explicit = [];

  if (process.env.BAZIMYA_PYTHON) {
    explicit.push({ binary: process.env.BAZIMYA_PYTHON, source: 'BAZIMYA_PYTHON' });
  }

  const pinned = pinnedInPackageJson(cwd);

  if (pinned) {
    explicit.push({ binary: pinned, source: 'the "bazimya.python" key in package.json' });
  }

  for (const entry of explicit) {
    const found = inspect(entry.binary);

    if (found && found.supported) {
      return found;
    }

    if (found) {
      throw handled(
        `Python at ${entry.binary} is ${found.version}; Bazimya needs ` +
          `${MINIMUM_PYTHON.join('.')} or newer.\n(set by ${entry.source})`
      );
    }

    throw handled(
      `Could not run Python at ${entry.binary}\n(set by ${entry.source}).`
    );
  }

  const search = virtualenvCandidates(cwd).concat(candidatePaths());

  for (const binary of search) {
    if (tried.has(binary)) {
      continue;
    }

    tried.add(binary);

    const found = inspect(binary);

    if (!found) {
      continue;
    }

    if (found.supported) {
      return found;
    }

    tooOld.push(`${binary} (${found.version})`);
  }

  const lines = [
    `Bazimya needs Python ${MINIMUM_PYTHON.join('.')} or newer, and none was found.`,
    '',
  ];

  if (tooOld.length > 0) {
    lines.push('These were found but are too old:');
    for (const entry of tooOld) {
      lines.push(`  ${entry}`);
    }
    lines.push('');
  }

  if (process.platform === 'darwin') {
    lines.push('Install it with:  brew install python');
  } else if (process.platform === 'win32') {
    lines.push('Download it from: https://www.python.org/downloads/');
  } else {
    lines.push('Install it with:  sudo apt install python3 python3-venv');
  }

  lines.push('');
  lines.push('Already installed somewhere unusual? Point Bazimya at it:');
  lines.push('  BAZIMYA_PYTHON=/full/path/to/python3 npx bazimya serve');

  throw handled(lines.join(os.EOL));
}

function handled(message) {
  const error = new Error(message);
  error.bazimyaHandled = true;

  return error;
}

module.exports = { findPython, inspect, MINIMUM_PYTHON };
