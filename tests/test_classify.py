from __future__ import annotations

import json
import subprocess
import sys

import classify
from conftest import EXAMPLES_DIR, FIXTURES_DIR, ROOT


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text()


def classify_text(text: str) -> list[classify.ToolReport]:
    return classify.build_reports(text)


def test_ruff_ok() -> None:
    reports = classify_text(read_fixture("ruff_ok.txt"))
    assert reports[0].status == "ok"


def test_ruff_found_count() -> None:
    reports = classify_text(read_fixture("ruff_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_ruff_config_broken() -> None:
    reports = classify_text(read_fixture("ruff_config_broken.txt"))
    assert reports[0].status == "config-broken"


def test_ruff_tool_missing() -> None:
    reports = classify_text(read_fixture("ruff_tool_missing.txt"))
    assert reports[0].status == "tool-missing"


def test_mypy_aborted() -> None:
    reports = classify_text(read_fixture("mypy_aborted.txt"))
    assert reports[0].status == "aborted"


def test_mypy_ok() -> None:
    reports = classify_text(read_fixture("mypy_ok.txt"))
    assert reports[0].status == "ok"


def test_mypy_found_count() -> None:
    reports = classify_text(read_fixture("mypy_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_pylint_found_count() -> None:
    reports = classify_text(read_fixture("pylint_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_vulture_found_count() -> None:
    reports = classify_text(read_fixture("vulture_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_bandit_found_count() -> None:
    reports = classify_text(read_fixture("bandit_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_eslint_found_count() -> None:
    reports = classify_text(read_fixture("eslint_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_eslint_tool_missing_sentinel() -> None:
    reports = classify_text(read_fixture("eslint_tool_missing.txt"))
    assert reports[0].status == "tool-missing"


def test_prettier_found_count() -> None:
    reports = classify_text(read_fixture("prettier_found.txt"))
    assert reports[0].status == "found"
    assert reports[0].count == 1


def test_precommit_ok() -> None:
    reports = classify_text(read_fixture("precommit_ok.txt"))
    assert reports[0].status == "ok"


def test_precommit_found_reports_mutated_detail() -> None:
    reports = classify_text(read_fixture("precommit_found.txt"))
    assert reports[0].status == "found"
    assert "mutated: 1 files" in reports[0].detail


def test_precommit_skipped() -> None:
    reports = classify_text(read_fixture("precommit_skipped.txt"))
    assert reports[0].status == "skipped"


def test_semgrep_skipped() -> None:
    reports = classify_text(read_fixture("semgrep_skipped.txt"))
    assert reports[0].status == "skipped"


def test_precedence_tool_missing_wins_over_found() -> None:
    reports = classify_text(read_fixture("precedence_tool_missing_wins.txt"))
    assert reports[0].status == "tool-missing"


def test_nonzero_exit_with_unparsable_output_never_classifies_as_ok() -> None:
    reports = classify_text(read_fixture("unknown_status.txt"))
    assert reports[0].status != "ok"
    assert reports[0].status == "unknown"


def test_dump_config_selects_legacy_profile_and_resolves_ruff_config() -> None:
    config_file = EXAMPLES_DIR / ".polylint.toml"
    target = str(EXAMPLES_DIR / "src" / "legacy" / "old_module.py")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "classify.py"),
            "--dump-config",
            str(config_file),
            "--target",
            target,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    values = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert values["POLYLINT_PROFILE"] == "legacy"
    assert "flake8" not in values["POLYLINT_TOOLS_DISABLED"].split(",")
    assert "mypy" in values["POLYLINT_TOOLS_DISABLED"].split(",")
    assert values["RUFF_CONFIG"].endswith("ruff.example.toml")


def test_dump_config_without_matching_profile_uses_defaults() -> None:
    config_file = EXAMPLES_DIR / ".polylint.toml"
    target = str(EXAMPLES_DIR / "src" / "app.py")
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "classify.py"),
            "--dump-config",
            str(config_file),
            "--target",
            target,
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    values = dict(line.split("=", 1) for line in result.stdout.strip().splitlines())
    assert values["POLYLINT_PROFILE"] == ""
    disabled = values["POLYLINT_TOOLS_DISABLED"].split(",")
    assert "flake8" in disabled
    assert "pylint" not in disabled


def test_json_format_cli() -> None:
    fixture = FIXTURES_DIR / "ruff_found.txt"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "classify.py"), str(fixture), "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)
    assert any(
        item["tool"] == "ruff" and item["status"] == "found" and item["count"] >= 1 for item in data
    )


def test_exit_code_flag_returns_1_when_findings_present() -> None:
    fixture = FIXTURES_DIR / "ruff_found.txt"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "classify.py"), str(fixture), "--exit-code"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1


def test_exit_code_flag_returns_0_when_clean() -> None:
    fixture = FIXTURES_DIR / "ruff_ok.txt"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "classify.py"), str(fixture), "--exit-code"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_default_exit_code_is_zero_even_with_findings() -> None:
    fixture = FIXTURES_DIR / "ruff_found.txt"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "classify.py"), str(fixture)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0


def test_markdown_format_lists_every_tool() -> None:
    text = read_fixture("ruff_found.txt") + read_fixture("mypy_ok.txt")
    reports = classify_text(text)
    output = classify.render_markdown(reports)
    assert "ruff" in output
    assert "mypy" in output
