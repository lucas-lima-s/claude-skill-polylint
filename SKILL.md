---
name: polylint
description: "Runs a project's own lint stack on a file or directory, reports an honest per-tool status and proposes fixes for approval. Only on an explicit request: 'lint this', 'run lint', 'check code style', '/polylint', 'rode lint', 'valide os lints'."
---

# polylint - honest three-phase lint runner

## What it does

A single invocation runs up to three phases in a fixed order, each with a
different permission model:

| Phase | What it does | Permission |
|---|---|---|
| **1 - Pre-commit replay (opt-in)** | Runs the target repository's own `.pre-commit-config.yaml` against the target, only with `--precommit`. Hooks can and will mutate files (formatters, `--fix` variants, whitespace fixers), and a remote hook is downloaded and executed from its repository. | **Only when the user asked for it.** Say first that hooks may rewrite files; the runner prints a warning listing every remote hook source. |
| **2 - Read-only analysis** | Every enabled analyzer (ruff, pylint, mypy, vulture, bandit, and any opt-in tool) runs in parallel, read-only. Reports findings only, never mutates. | **No permission needed - always runs.** |
| **3 - Approval-gated recommendations** | The agent enumerates the leftover findings from Phase 2 and asks which items to apply. Scope is semantic/structural changes: manual refactors, `--fix` on rules the pre-commit hooks didn't cover, `noqa`/`# type: ignore` suppressions, config adjustments. | **Ask per item (or per numbered group). Never apply silently, never in bulk without a per-item choice.** |

The permission split is the point: Phase 2 only reads, so it always runs;
Phase 1 changes files and may run third-party code, so it needs the user's
request; a Phase 3 recommendation has not been authorized by anyone yet, so
it always waits for an explicit answer.

## When to use / when not to

Use it when the user explicitly asks to lint, check style, or validate a
file or directory. Do not start it on your own after editing code; offer it
in one line instead.

Do not use it for:

- Generated or vendored trees (build output, bundlers' scratch directories,
  vendored dependency copies). Declare them in `exclude` under `[configs]` in
  `.polylint.toml` instead of running the tool stack against them.
- Anything a project's own `.polylint.toml` already lists in `exclude` -
  polylint skips the whole run for a target that matches one of those globs
  and says so, rather than reporting misleading findings.

## Invocation

Always route through the runner - never hand-compose parallel linter calls.
`<skill-dir>` is the directory that contains this SKILL.md:

```
bash "<skill-dir>/polylint.sh" <target> [flags]
```

On Windows from PowerShell, `bash` may resolve to WSL's `System32\bash.exe`, which cannot read Windows paths; call Git for Windows' bash explicitly (`& "$env:ProgramFiles\Git\bin\bash.exe" "<skill-dir>/polylint.sh" ...`).

One shell call total. The runner spawns every Phase 2 analyzer as a
background job internally and waits for all of them; the caller sees a
single command and a single, fixed-order report.

## Flags

| Flag | Default | Effect |
|---|---|---|
| `--config FILE` | auto-discovered | Use this `.polylint.toml` instead of walking up from the target. |
| `--profile NAME` | auto-matched | Force a specific `[[profiles]]` entry instead of glob-matching the target. |
| `--precommit` | off | Run Phase 1, the pre-commit replay (mutates files; see above). |
| `--no-precommit` | - | Accepted for compatibility; Phase 1 is already off unless `--precommit` is passed. |
| `--no-mypy` / `--no-pylint` / `--no-vulture` / `--no-bandit` | all on | Skip that analyzer. `ruff` is mandatory and has no opt-out flag. |
| `--flake8` / `--black` / `--isort` / `--pyright` / `--semgrep` | all off | Opt in to that analyzer. `--semgrep` downloads the `p/python` rules from the Semgrep registry, so it needs network access. |
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
"$POLYLINT_PY" -m pip install ruff pylint mypy vulture bandit pre-commit
"$POLYLINT_PY" -m pip install flake8 black isort pyright semgrep
```

`POLYLINT_PY` is the interpreter the runner uses (when it is unset, use
`python3` or `python` from `PATH` in its place). Install only after the user
agrees. `pre-commit`
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
