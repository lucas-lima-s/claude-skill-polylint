# Contributing

## Development setup

```bash
uv sync --dev
```

This installs pytest, ruff, pre-commit, pylint, mypy, vulture, and bandit
into a local `.venv/`.

## Running the checks

```bash
uv run pytest -q                    # unit + smoke tests
uv run ruff check .                 # lint
uv run ruff format --check .        # format check
bash -n polylint.sh                 # shell syntax
shellcheck -S warning polylint.sh   # shell lint (install shellcheck separately)
```

All of the above run in CI on every push and pull request; see
[.github/workflows/ci.yml](.github/workflows/ci.yml).

## Project layout

| Path | What it is |
|---|---|
| `polylint.sh` | The runner. Bash, POSIX-flavored where practical, `shellcheck -S warning`-clean. |
| `scripts/classify.py` | The status classifier and TOML config loader. Stdlib only. |
| `examples/sample-project/` | A tiny, deterministic fixture project used by the test suite and by the verification probes in `SKILL.md`. |
| `tests/` | pytest suite: fixture-driven unit tests for the classifier, plus an offline subprocess smoke test for the runner. |
| `config/*.example` | Reference configs referenced from `polylint.example.toml`'s comments and from the sample project. |
| `docs/` | The status taxonomy reference and a real captured example report. |

## Making a change

1. If you're changing `polylint.sh`, keep it `bash -n` and
   `shellcheck -S warning` clean - both are enforced in CI as a dedicated
   job.
2. If you're changing the status taxonomy or a finding pattern in
   `scripts/classify.py`, update `docs/statuses.md` alongside it, and add a
   fixture under `tests/fixtures/` exercising the new/changed branch.
3. Run `uv run pytest -q` and confirm every existing test still passes -
   the precedence order in `classify_block()` is deliberately strict and a
   change that reorders the `if` chain without a corresponding test update
   is the most likely way to silently regress the tool's core guarantee
   (a non-zero exit never reads as `ok`).
4. Run the verification probes at the bottom of `SKILL.md` against
   `examples/sample-project/` before considering a runner change done.

## Commit style

Conventional commits (`feat:`, `fix:`, `docs:`, `test:`, `chore:`, `ci:`),
one logical change per commit.

## Reporting an issue

Open a GitHub issue with the exact `polylint.sh` invocation, the relevant
`===== <tool> (exit=<code>) =====` block, and your `POLYLINT_*` environment
overrides (redact anything project-specific you don't want to share).
