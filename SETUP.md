# Setup

## Requirements

| Requirement | Why |
|---|---|
| `bash` (4+) | Runs `polylint.sh`. Ships by default on Linux/macOS; on Windows, Git for Windows' bundled `bash.exe` works fine. |
| Python 3.11+ | Runs `scripts/classify.py`, which uses the standard-library `tomllib` (Python 3.11+ only). |
| `pre-commit` | Only needed if the target repository has a `.pre-commit-config.yaml` you want Phase 1 to replay. |
| The analyzers you want to run | `ruff` (mandatory), plus any of `pylint`, `mypy`, `vulture`, `bandit`, `flake8`, `black`, `isort`, `pyright`, `semgrep` you enable. |
| `shellcheck` (optional, dev only) | Only needed to run the shell-lint job locally; CI installs it automatically. |

None of the above needs to be at a fixed, absolute path. The runner resolves
everything through `PATH` and a small set of environment variable
overrides - there is nothing machine-specific to edit before it works on a
new machine.

## Installing the skill

Clone the repository anywhere and expose the folder as `polylint` in the
skills directory of each agent you use (for example `~/.claude/skills`,
`~/.agents/skills` or `~/.gemini/config/skills`), as a symlink or a copy.
The skill calls `<skill-dir>/polylint.sh` relative to its own folder, so no
particular location is required.

```bash
git clone https://github.com/lucas-lima-s/claude-skill-polylint <skill-dir>
```

## Installing the analyzers

Install whichever of these you want available, on whatever interpreter
`POLYLINT_PY` will resolve to (default: the first of `python3`/`python` on
`PATH`):

```bash
"$POLYLINT_PY" -m pip install ruff pylint mypy vulture bandit pre-commit
"$POLYLINT_PY" -m pip install flake8 black isort pyright semgrep
```

The second line holds the optional, opt-in tools. When `POLYLINT_PY` is
unset, use the `python3` or `python` the runner would pick from `PATH`.

For JS/TS targets, `eslint` and `prettier` are resolved from the target
project's own `node_modules` (via `npx --no-install`) - nothing to install
globally unless you also want a standalone fallback toolchain (see
`POLYLINT_JS_DIR` below).

## Environment variables

All optional - the runner has sane, portable defaults for every one of
these:

| Variable | Default | Purpose |
|---|---|---|
| `POLYLINT_PY` | first of `python3`, `python` on `PATH` | Interpreter for `scripts/classify.py` and, unless a profile overrides it, for every Phase 2 Python tool invocation. |
| `POLYLINT_CONFIG_DIR` | `${XDG_CONFIG_HOME:-$HOME/.config}/polylint` | Fallback directory for a shared `polylint.toml` when no `.polylint.toml` is found walking up from the target. |
| `POLYLINT_JS_DIR` | unset | A standalone Node toolchain directory to fall back to for JS/TS targets when no in-project ESLint config is found. |
| `POLYLINT_RUFF_CMD`, `POLYLINT_PYLINT_CMD`, `POLYLINT_MYPY_CMD`, `POLYLINT_VULTURE_CMD`, `POLYLINT_BANDIT_CMD`, `POLYLINT_FLAKE8_CMD`, `POLYLINT_BLACK_CMD`, `POLYLINT_ISORT_CMD`, `POLYLINT_PYRIGHT_CMD`, `POLYLINT_SEMGREP_CMD`, `POLYLINT_PRECOMMIT_CMD` | unset (falls back to `"$PY" -m <module>`) | Override the exact command used to invoke that tool. |

## Validating the install

```bash
bash "<skill-dir>/polylint.sh" examples/sample-project/src/app.py
```

Expected: a `ruff` block reporting `F401` for the unused `os` import, plus
whichever other analyzers you have installed. If a block reads
`tool-missing`, install that analyzer (see above) and re-run.

## Cache

`pre-commit` itself caches hook environments at `~/.cache/pre-commit/` (only
relevant for *remote* hooks - the sample project's own hook is `repo: local`
and needs no cache at all). Nothing in this repository writes any other
persistent cache; `.ruff_cache/`, `.mypy_cache/`, and `.pytest_cache/` are
ordinary tool caches under the working directory, already covered by
`.gitignore`.
