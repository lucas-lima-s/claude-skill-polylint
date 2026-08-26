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
    return shutil.which("bash") or "bash"


def _run_polylint(target: str, *extra_args: str, cwd: Path) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["POLYLINT_PY"] = sys.executable
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
        "--no-mypy",
        "--no-pylint",
        "--no-bandit",
        "--no-vulture",
        cwd=project_dir,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "===== precommit" in result.stdout
    assert "files were modified by this hook" in result.stdout


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
