# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

## [0.1.0] - 2026-08-25

### Added

- Three-phase runner (`polylint.sh`): pre-commit replay, parallel read-only analysis, approval-gated recommendations.
- Honest per-tool status classifier (`scripts/classify.py`) with a fixed precedence: `tool-missing` > `config-broken` > `aborted` > `skipped` > `found` > `ok`.
- Glob-matched profiles (`[[profiles]]` in `.polylint.toml`) to route a subtree to a different interpreter or tool subset.
- Sample project under `examples/sample-project/` with deterministic, offline findings for Python, JS, and a `repo: local` pre-commit hook.
- Test suite covering every status branch, precedence rules, per-tool finding counts, and an offline runner smoke test.
- GitHub Actions CI: cross-platform test matrix plus a shellcheck job.
