# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Changed

- Phase 1 (pre-commit replay) is opt-in with `--precommit`; `--no-precommit`
  stays accepted as a no-op. The runner warns on stderr and in the report
  when the config uses remote hooks.
- The skill triggers only on an explicit request and calls the runner
  relative to its own directory instead of a Claude-only path.
- Docker hint uses the `semgrep/semgrep` image; SKILL.md notes that
  `--semgrep` needs network access.
- Install commands use `"$POLYLINT_PY" -m pip`.
- Verification probes moved from SKILL.md to CONTRIBUTING.md.

### Fixed

- A target path containing `'` no longer breaks the WSL semgrep command.

## [0.1.0] - 2026-08-25

### Added

- Three-phase runner (`polylint.sh`): pre-commit replay, parallel read-only analysis, approval-gated recommendations.
- Honest per-tool status classifier (`scripts/classify.py`) with a fixed precedence: `tool-missing` > `config-broken` > `aborted` > `skipped` > `found` > `ok`.
- Glob-matched profiles (`[[profiles]]` in `.polylint.toml`) to route a subtree to a different interpreter or tool subset.
- Sample project under `examples/sample-project/` with deterministic, offline findings for Python, JS, and a `repo: local` pre-commit hook.
- Test suite covering every status branch, precedence rules, per-tool finding counts, and an offline runner smoke test.
- GitHub Actions CI: cross-platform test matrix plus a shellcheck job.
