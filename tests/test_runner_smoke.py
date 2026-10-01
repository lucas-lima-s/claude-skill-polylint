from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from conftest import EXAMPLES_DIR, ROOT


def _prepare_repo(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    project_dir = workspace / "examples" / "sample-project"
    project_dir.parent.mkdir(parents=True)
    shutil.copytree(EXAMPLES_DIR, project_dir)
    shutil.copytree(ROOT / "config", workspace / "config")

    subprocess.run(["git", "init", "-q"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=project_dir, check=True)
    subprocess.run(["git", "add", "-A"], cwd=project_dir, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "initial"], cwd=project_dir, check=True)
    return project_dir


def _bash_executable() -> str:
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            candidate = Path(git).resolve().parents[1] / "bin" / "bash.exe"
            if candidate.is_file():
                return str(candidate)
    return shutil.which("bash") or "bash"


def _project_python() -> str:
    for candidate in (
        ROOT / ".venv" / "Scripts" / "python.exe",
        ROOT / ".venv" / "bin" / "python",
    ):
        if candidate.exists():
            return str(candidate)
    return sys.executable


def _run_polylint(target: str, *extra_args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["POLYLINT_PY"] = _project_python()
    cmd = [_bash_executable(), str(ROOT / "polylint.sh"), target, *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)


def test_phase2_only_reports_ruff_f401(tmp_path: Path) -> None:
    project_dir = _prepare_repo(tmp_path)
    result = _run_polylint(
        "src/app.py",
        "--no-precommit",
        "--no-mypy",
        "--no-pylint",
        "--no-bandit",
        "--no-vulture",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "===== ruff (exit=1) =====" in result.stdout
    assert "F401" in result.stdout


def test_phase1_runs_local_precommit_hook_and_reports_mutation(tmp_path: Path) -> None:
    project_dir = _prepare_repo(tmp_path)
    result = _run_polylint(
        "src/app.py",
        "--precommit",
        "--no-mypy",
        "--no-pylint",
        "--no-bandit",
        "--no-vulture",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "===== precommit" in result.stdout
    assert "files were modified by this hook" in result.stdout
    assert "remote pre-commit hooks" not in result.stdout


def test_phase1_is_opt_in_and_leaves_files_untouched(tmp_path: Path) -> None:
    project_dir = _prepare_repo(tmp_path)
    before = (project_dir / "src" / "app.py").read_bytes()
    result = _run_polylint(
        "src/app.py",
        "--no-mypy",
        "--no-pylint",
        "--no-bandit",
        "--no-vulture",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "===== precommit" not in result.stdout
    assert (project_dir / "src" / "app.py").read_bytes() == before


def test_phase1_warns_about_remote_hooks(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PRE_COMMIT_HOME", str(tmp_path / "pre-commit-home"))
    project_dir = _prepare_repo(tmp_path)
    config = project_dir / ".pre-commit-config.yaml"
    config.write_text(
        "repos:\n"
        "  - repo: https://example.invalid/polylint-test-hooks\n"
        "    rev: v0\n"
        "    hooks:\n"
        "      - id: x\n",
        encoding="utf-8",
    )
    result = _run_polylint(
        "src/app.py",
        "--precommit",
        "--no-mypy",
        "--no-pylint",
        "--no-bandit",
        "--no-vulture",
        cwd=project_dir,
    )
    assert "remote pre-commit hooks are downloaded and executed from" in result.stdout
    assert "https://example.invalid/polylint-test-hooks" in result.stderr


def test_legacy_profile_selected_for_legacy_target(tmp_path: Path) -> None:
    project_dir = _prepare_repo(tmp_path)
    result = _run_polylint(
        "src/legacy/old_module.py",
        "--no-precommit",
        "--no-mypy",
        "--no-pylint",
        "--no-vulture",
        "--no-bandit",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "profile: legacy" in result.stdout


def test_eslint_reports_tool_missing_without_node_modules(tmp_path: Path) -> None:
    project_dir = _prepare_repo(tmp_path)
    result = _run_polylint("src/util.js", "--no-precommit", cwd=project_dir)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "===== eslint (exit=tool-missing) =====" in result.stdout
