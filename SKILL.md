---
name: polylint
description: Run the project's own lint stack over a file or directory in three phases - replay the repo's pre-commit hooks, run read-only analyzers in parallel, then propose fixes for approval - and report an honest per-tool status instead of a silent pass. Use whenever code has just been written or edited and needs validation, or when the user asks to lint, check style, or validate a file. Triggers on "lint this", "run lint", "check code style", "validate this file", "rode lint", "valide os lints", "/polylint".
---

# polylint - honest three-phase lint runner

## What it does

A single invocation runs three phases in a fixed order, each with a
different permission model:

| Phase | What it does | Permission |
|---|---|---|
| **1 - Pre-commit replay** | Runs the target repository's own `.pre-commit-config.yaml` against the target. Hooks can and will mutate files (formatters, `--fix` variants, whitespace fixers). | **No permission needed - always runs.** The user already authorized these hooks the moment they were checked into the repository's own config. |
| **2 - Read-only analysis** | Every enabled analyzer (ruff, pylint, mypy, vulture, bandit, and any opt-in tool) runs in parallel, read-only. Reports findings only, never mutates. | **No permission needed - always runs.** |
| **3 - Approval-gated recommendations** | Claude enumerates the leftover findings from Phase 2 and asks which items to apply. Scope is semantic/structural changes: manual refactors, `--fix` on rules the pre-commit hooks didn't cover, `noqa`/`# type: ignore` suppressions, config adjustments. | **Ask per item (or per numbered group). Never apply silently, never in bulk without a per-item choice.** |

The permission split is the point: a hook the team already committed to the
repository has already been authorized by the act of committing it, so
replaying it needs no fresh confirmation. A Phase 3 recommendation has not
been authorized by anyone yet, so it always waits for an explicit answer.

## When to use / when not to

Use it whenever code has just been written or edited and needs validating
before it's handed back, or whenever a user explicitly asks to lint, check
style, or validate a file or directory.

Do not use it for:

- Generated or vendored trees (build output, bundlers' scratch directories,
  vendored dependency copies). Declare them in `exclude` under `[configs]` in
  `.polylint.toml` instead of running the tool stack against them.
- Anything a project's own `.polylint.toml` already lists in `exclude` -
  polylint skips the whole run for a target that matches one of those globs
  and says so, rather than reporting misleading findings.

## Invocation

Always route through the runner - never hand-compose parallel linter calls:

```
bash "$HOME/.claude/skills/polylint/polylint.sh" <target> [flags]
```

One Bash call total. The runner spawns every Phase 2 analyzer as a
background job internally and waits for all of them; the caller sees a
single command and a single, fixed-order report.

## Flags

| Flag | Default | Effect |
|---|---|---|
| `--config FILE` | auto-discovered | Use this `.polylint.toml` instead of walking up from the target. |
| `--profile NAME` | auto-matched | Force a specific `[[profiles]]` entry instead of glob-matching the target. |
| `--no-precommit` | Phase 1 on | Skip the pre-commit replay entirely. |
| `--no-mypy` / `--no-pylint` / `--no-vulture` / `--no-bandit` | all on | Skip that analyzer. `ruff` is mandatory and has no opt-out flag. |
| `--flake8` / `--black` / `--isort` / `--pyright` / `--semgrep` | all off | Opt in to that analyzer. |
| `--json` | off | Pipe the report through `scripts/classify.py --format json` instead of printing raw tool output. |
| `--version` | - | Print the runner version and exit. |

## Configuration and profiles

Config discovery walks up from the target looking for `.polylint.toml`; if
none is found it falls back to `$POLYLINT_CONFIG_DIR/polylint.toml`
(default `${XDG_CONFIG_HOME:-$HOME/.config}/polylint`), then to each tool's
own built-in config auto-discovery. See [README.md](README.md) for the full
`POLYLINT_*` environment variable reference and the TOML schema.

A `.polylint.toml` can declare `[[profiles]]` entries: glob-matched routes
that override the interpreter and/or the enabled tool set for a subtree. The
shipped example routes anything under `**/legacy/**` to a narrower
`flake8`-only pipeline with its own interpreter - useful for an older area of
a codebase that the main tool stack isn't tuned for. The header of every
report prints `profile: <name>` (or `profile: default` when nothing matched)
so it's always clear which route was taken.

## Status classification

Every tool's outcome is classified into exactly one of six statuses, in this
precedence order (full detail in [docs/statuses.md](docs/statuses.md)):

1. `tool-missing` - the binary/module isn't there.
2. `config-broken` - the tool's own config file failed to parse or apply.
3. `aborted` - the tool crashed or bailed out mid-run (a real finding, not a
   skill failure - e.g. mypy's "errors prevented further checking").
4. `skipped` - the phase was never attempted (no `.pre-commit-config.yaml`
   found; semgrep unavailable with no install path).
5. `found` - real findings, count included.
6. `ok` - the tool ran clean.

**Hard rule: never report a linter as clean when it errored.** A broken
config is reported as `config-broken` with the config file, not folded into
a false `ok`. Anything unparseable with a non-zero exit code is `unknown`,
never `ok`.

## Output format

```
# polylint: <target>
profile: <name>
lang: <py|js>

===== <tool> (exit=<code>) =====
<raw tool output, verbatim>

===== <tool> (exit=<code>) =====
...
```

One `=====` block per tool, in a fixed order, always present when that tool
was enabled - even when its output is empty (`(no output)`) or its exit code
is a sentinel like `skipped` or `tool-missing`. Pipe the whole report through
`scripts/classify.py` to turn it into a compact per-tool status table
(`--format markdown`, the default) or a machine-readable list
(`--format json`). See [docs/example-report.md](docs/example-report.md) for
a real captured run.

## Approval gate

After presenting the report, end the turn asking which numbered Phase 3
items to apply - never apply silently, never in bulk without a per-item
answer. If the user replies with a specific list, apply only those; if they
say "all", apply everything listed. Formatter-only items (whitespace, import
order, quote style) never appear in the Phase 3 list - formatters are
manual-only and only run when explicitly requested (`--black`, `--isort`, or
a direct request to run `ruff format`).

## Installing missing tools

```
python -m pip install ruff
python -m pip install pylint
python -m pip install mypy
python -m pip install vulture
python -m pip install bandit
python -m pip install flake8
python -m pip install black
python -m pip install isort
python -m pip install pyright
python -m pip install semgrep
python -m pip install pre-commit
```

No absolute interpreter paths - each command targets whichever Python
`POLYLINT_PY` (or `python3`/`python` on `PATH`) resolves to. `pre-commit`
downloads its hook environments on first run for any *remote* hook - a
`repo: local` hook (the kind this project's own examples use) needs no
download at all.

## Gotchas

- **`ruff` with `select = ["ALL"]`** produces a lot of volume on a large or
  legacy file. For a targeted audit, suggest a narrower `--select E,F,B` (or
  point `.polylint.toml`'s `[configs].ruff` at a narrower config) instead of
  running the full rule set.
- **pylint's `ignored-modules`** (under `[TYPECHECK]` in a project's
  `pylintrc`) suppresses cross-package import noise. A new `E0401` for a
  module not already on that list is a real finding - fix the list, not the
  source file, if the import is legitimate.
- **vulture's `--ignore-names` and `--min-confidence`** cover common
  framework hooks and unittest fixtures (`setUp*`, `tearDown*`, `test_*`,
  etc.). If a real function is flagged, either it doesn't match the ignored
  pattern (a naming finding, not a false positive) or `--min-confidence`
  needs lowering for a deeper, noisier pass.
- **mypy's "errors prevented further checking"** means the target itself has
  a fatal type error early in the file (e.g. a duplicate `@overload`); mypy
  bails out mid-file. Treat this as a real code bug and surface it, not as a
  runner malfunction. The runner also adds `--follow-imports=skip`
  automatically when no `[configs].mypy` config is set, since a bare mypy
  invocation without a project's own `mypy_path` otherwise floods on
  unrelated cross-package imports; when that flag is in effect the header
  says so.

## Verification probes

Run these after any change to `polylint.sh` or `scripts/classify.py`,
against `examples/sample-project/`:

1. `polylint.sh examples/sample-project/src/app.py --no-precommit` - ruff,
   pylint, mypy, vulture, bandit all fire; ruff reports `F401` for the
   unused `os` import.
2. `polylint.sh examples/sample-project/src/app.py --no-precommit --no-mypy --no-pylint --no-bandit --no-vulture` -
   only `ruff` runs.
3. `polylint.sh examples/sample-project/src/legacy/old_module.py --no-precommit --no-mypy --no-pylint --no-vulture --no-bandit` -
   header shows `profile: legacy`; only `flake8` (the profile's declared
   tool set) is attempted.
4. `polylint.sh examples/sample-project/src/util.js --no-precommit` - no
   `package.json`/ESLint config is present, so the `eslint` block reports
   `tool-missing` rather than a false `ok`.
5. `polylint.sh examples/sample-project/src/app.py` (Phase 1 enabled, inside
   a git repository) - the `repo: local` pre-commit hook strips the
   deliberately trailing-whitespace line and the `precommit` block reports
   the mutated file.
6. `POLYLINT_RUFF_CMD='definitely-not-a-real-tool' polylint.sh examples/sample-project/src/app.py --no-precommit` -
   the `ruff` block reports `tool-missing`, never `ok`.
7. `polylint.sh examples/sample-project/src/app.py --no-precommit --json | python scripts/classify.py --format json` (or
   pass `--json` once and skip the second call) - valid JSON with one entry
   per tool.
8. `python scripts/classify.py --dump-config examples/sample-project/.polylint.toml --target examples/sample-project/src/legacy/old_module.py` -
   prints `POLYLINT_PROFILE=legacy` and a `POLYLINT_TOOLS_DISABLED` list that
   does not contain `flake8`.
9. `python scripts/classify.py tests/fixtures/ruff_config_broken.txt` -
   `config-broken`, not `found` or `ok`.
10. `python scripts/classify.py tests/fixtures/mypy_aborted.txt` - `aborted`.
