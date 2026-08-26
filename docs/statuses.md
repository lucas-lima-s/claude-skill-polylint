# Status taxonomy

`scripts/classify.py` turns every `===== <tool> (exit=<code>) =====` block from
`polylint.sh` into exactly one of six statuses. The list below is precedence
order: the first rule that matches wins, and the test suite pins this order.

1. **`tool-missing`** - the block matches `No module named`,
   `ModuleNotFoundError`, `command not found`, `No such file or directory`,
   `is not recognized as an internal or external command`,
   `not found in PATH`, or the runner's own `tool-missing` sentinel (used when
   the runner itself already knows the tool can't run, e.g. no ESLint config
   found and no fallback directory configured).
2. **`config-broken`** - the block matches `Failed to parse`, `unknown field`,
   `TOML parse error`, `Invalid configuration`, `error: invalid value`,
   `unrecognized arguments`, `Config file .* not found`,
   `Error in provided regular expression`, or `no such option`.
3. **`aborted`** - the block matches `errors prevented further checking`,
   `INTERNAL ERROR`, `Fatal error`, `Traceback (most recent call last)`, or the
   exit code is `124` or `137` (timeout / killed).
4. **`skipped`** - the block body starts with `skipped:`, or the exit field
   is literally `skipped` (used when a phase was never attempted, e.g. no
   `.pre-commit-config.yaml` found, or semgrep has no install path available).
5. **`found`** - exit code is non-zero and at least one line matches the
   tool's finding pattern (or, when a tool has no dedicated pattern, at least
   one non-empty line was produced).
6. **`ok`** - exit code is `0` and no finding lines were produced.

Anything that doesn't fit one of the six is reported as **`unknown`**, never
as `ok`. This is the invariant the test suite enforces above all others:

> No branch can ever downgrade a non-zero exit with unparsed output into `ok`.

A linter that crashes in a way nobody anticipated should read as "something is
wrong here, go look" - not as a silent pass.

## Per-tool finding patterns

| Tool | Pattern (anchored at line start) |
|---|---|
| ruff / flake8 | `<file>:<line>:<col>: <CODE> ` |
| pylint | `<file>:<line>:<col>: <C####>: ` |
| mypy | `<file>:<line>: error\|warning: ` (notes are excluded) |
| vulture | `<file>:<line>: unused ` |
| bandit | `>> Issue: [` |
| pyright | `<file>:<line>:<col> - error\|warning: ` |
| eslint | `  <line>:<col>  error\|warning  ` |
| prettier | `[warn] ` |
| black | `would reformat ` |
| isort | `ERROR: ... Imports are incorrectly sorted` |
| precommit | hook lines `<hook name>....Passed\|Failed\|Skipped`; a `found` precommit block also reports `mutated: <n> files` by counting `- files were modified by this hook` |

A tool without a dedicated pattern (for example semgrep, whose text output
format varies with the ruleset) falls back to "at least one non-empty line
counts as a finding" - still subject to the same precedence order above, so a
crash still reads as `tool-missing`/`config-broken`/`aborted` first.
