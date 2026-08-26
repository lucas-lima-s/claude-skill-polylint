from __future__ import annotations

import argparse
import fnmatch
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

BLOCK_HEADER_RE = re.compile(r"^===== (?P<tool>\S+) \(exit=(?P<code>[^)]*)\) =====$")

TOOL_MISSING_RE = re.compile(
    r"No module named"
    r"|ModuleNotFoundError"
    r"|command not found"
    r"|No such file or directory"
    r"|is not recognized as an internal or external command"
    r"|not found in PATH"
)

CONFIG_BROKEN_RE = re.compile(
    r"Failed to parse"
    r"|unknown field"
    r"|TOML parse error"
    r"|Invalid configuration"
    r"|error: invalid value"
    r"|unrecognized arguments"
    r"|Config file .* not found"
    r"|Error in provided regular expression"
    r"|no such option"
)

ABORTED_RE = re.compile(
    r"errors prevented further checking"
    r"|INTERNAL ERROR"
    r"|Fatal error"
    r"|Traceback \(most recent call last\)"
)

ABORTED_EXIT_CODES = frozenset({"124", "137"})

FINDING_PATTERNS: dict[str, re.Pattern[str]] = {
    "ruff": re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]+\d+) "),
    "flake8": re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]+\d+) "),
    "pylint": re.compile(r"^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>[A-Z]\d{4}): "),
    "mypy": re.compile(r"^(?P<file>.+?):(?P<line>\d+): (?P<kind>error|warning): "),
    "vulture": re.compile(r"^(?P<file>.+?):(?P<line>\d+): unused "),
    "bandit": re.compile(r"^>> Issue: \["),
    "pyright": re.compile(
        r"^\s*(?P<file>.+?):(?P<line>\d+):(?P<col>\d+) - (?P<kind>error|warning): "
    ),
    "eslint": re.compile(r"^\s+(?P<line>\d+):(?P<col>\d+)\s+(?P<kind>error|warning)\s+"),
    "prettier": re.compile(r"^\[warn\] "),
    "black": re.compile(r"^would reformat "),
    "isort": re.compile(r"^ERROR: .* Imports are incorrectly sorted"),
}

PRECOMMIT_HOOK_RE = re.compile(r"^(?P<hook>.+?)\.{2,}(?P<result>Passed|Failed|Skipped)$")
PRECOMMIT_MUTATED_RE = re.compile(r"- files were modified by this hook")

DEFAULT_TOGGLE_TOOLS = frozenset({"pylint", "mypy", "vulture", "bandit"})
OPT_IN_TOOLS = frozenset({"flake8", "black", "isort", "pyright", "semgrep"})
ALL_TOGGLE_TOOLS = DEFAULT_TOGGLE_TOOLS | OPT_IN_TOOLS

KNOWN_TOP_KEYS = frozenset({"python", "tools", "configs", "profiles"})
KNOWN_PYTHON_KEYS = frozenset({"interpreter"})
KNOWN_TOOLS_KEYS = frozenset({"disabled"})
KNOWN_CONFIGS_KEYS = frozenset({"ruff", "pylint", "mypy", "flake8", "exclude"})
KNOWN_PROFILE_KEYS = frozenset({"name", "match", "interpreter", "tools"})


@dataclass
class ToolReport:
    tool: str
    exit_code: str
    status: str
    count: int = 0
    detail: str = ""


def split_blocks(text: str) -> list[tuple[str, str, list[str]]]:
    blocks: list[tuple[str, str, list[str]]] = []
    current_tool: str | None = None
    current_code = ""
    current_lines: list[str] = []
    for line in text.splitlines():
        match = BLOCK_HEADER_RE.match(line)
        if match:
            if current_tool is not None:
                blocks.append((current_tool, current_code, current_lines))
            current_tool = match.group("tool")
            current_code = match.group("code")
            current_lines = []
        elif current_tool is not None:
            current_lines.append(line)
    if current_tool is not None:
        blocks.append((current_tool, current_code, current_lines))
    return blocks


def count_precommit(lines: list[str]) -> tuple[int, str]:
    hooks_failed = 0
    mutated = 0
    for line in lines:
        match = PRECOMMIT_HOOK_RE.match(line)
        if match and match.group("result") == "Failed":
            hooks_failed += 1
        if PRECOMMIT_MUTATED_RE.search(line):
            mutated += 1
    return hooks_failed, f"mutated: {mutated} files"


def count_findings(tool: str, lines: list[str]) -> tuple[int, str]:
    if tool == "precommit":
        return count_precommit(lines)
    pattern = FINDING_PATTERNS.get(tool)
    if pattern is None:
        significant = [line for line in lines if line.strip()]
        return len(significant), ""
    count = sum(1 for line in lines if pattern.match(line))
    return count, ""


def classify_block(tool: str, exit_code: str, lines: list[str]) -> ToolReport:
    body = "\n".join(lines)

    if exit_code == "tool-missing" or TOOL_MISSING_RE.search(body):
        return ToolReport(tool, exit_code, "tool-missing")

    if CONFIG_BROKEN_RE.search(body):
        return ToolReport(tool, exit_code, "config-broken")

    if ABORTED_RE.search(body) or exit_code in ABORTED_EXIT_CODES:
        return ToolReport(tool, exit_code, "aborted")

    if exit_code == "skipped" or body.strip().startswith("skipped:"):
        return ToolReport(tool, exit_code, "skipped")

    count, detail = count_findings(tool, lines)

    if exit_code != "0" and count > 0:
        return ToolReport(tool, exit_code, "found", count=count, detail=detail)

    if exit_code == "0" and count == 0:
        return ToolReport(tool, exit_code, "ok", detail=detail)

    if exit_code == "0" and count > 0:
        return ToolReport(tool, exit_code, "found", count=count, detail=detail)

    return ToolReport(tool, exit_code, "unknown", detail=detail)


def build_reports(text: str) -> list[ToolReport]:
    return [classify_block(tool, code, lines) for tool, code, lines in split_blocks(text)]


def render_markdown(reports: list[ToolReport]) -> str:
    lines = [
        "# polylint status report",
        "",
        "| tool | status | exit | count |",
        "|---|---|---|---|",
    ]
    for report in reports:
        lines.append(f"| {report.tool} | {report.status} | {report.exit_code} | {report.count} |")
    return "\n".join(lines) + "\n"


def render_json(reports: list[ToolReport]) -> str:
    payload = [
        {
            "tool": report.tool,
            "exit": report.exit_code,
            "status": report.status,
            "count": report.count,
            "detail": report.detail,
        }
        for report in reports
    ]
    return json.dumps(payload, indent=2) + "\n"


def warn_unknown_keys(section: str, data: dict, known: frozenset[str]) -> None:
    for key in data:
        if key not in known:
            print(f"classify.py: warning: unknown key '{key}' in [{section}]", file=sys.stderr)


def match_profile(profiles: list[dict], target: str, profile_override: str) -> dict | None:
    normalized_target = target.replace("\\", "/") if target else ""
    for profile in profiles:
        warn_unknown_keys("profiles", profile, KNOWN_PROFILE_KEYS)
        name = profile.get("name", "")
        if profile_override:
            if name == profile_override:
                return profile
            continue
        if not normalized_target:
            continue
        for pattern in profile.get("match", []):
            if fnmatch.fnmatch(normalized_target, pattern):
                return profile
    return None


def resolve_config_path(config_dir: Path, value: str) -> str:
    if not value:
        return ""
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = config_dir / candidate
    return str(candidate.resolve()).replace("\\", "/")


def dump_config(config_path: str, target: str, profile_override: str) -> None:
    config_dir = Path(config_path).resolve().parent
    with open(config_path, "rb") as handle:
        data = tomllib.load(handle)

    warn_unknown_keys("top-level", data, KNOWN_TOP_KEYS)
    python_section = data.get("python", {})
    warn_unknown_keys("python", python_section, KNOWN_PYTHON_KEYS)
    tools_section = data.get("tools", {})
    warn_unknown_keys("tools", tools_section, KNOWN_TOOLS_KEYS)
    configs_section = data.get("configs", {})
    warn_unknown_keys("configs", configs_section, KNOWN_CONFIGS_KEYS)
    profiles = data.get("profiles", [])

    global_disabled = set(tools_section.get("disabled", []))
    interpreter = python_section.get("interpreter", "")

    matched = match_profile(profiles, target, profile_override)

    profile_name = matched.get("name", "") if matched else ""
    if matched and matched.get("interpreter"):
        interpreter = matched["interpreter"]

    if matched and "tools" in matched:
        enabled = set(matched["tools"])
        effective_disabled = (ALL_TOGGLE_TOOLS - enabled) | global_disabled
    else:
        effective_disabled = set(OPT_IN_TOOLS) | global_disabled

    effective_disabled &= ALL_TOGGLE_TOOLS

    lines = [
        f"POLYLINT_PROFILE={profile_name}",
        f"POLYLINT_TOOLS_DISABLED={','.join(sorted(effective_disabled))}",
        f"RUFF_CONFIG={resolve_config_path(config_dir, configs_section.get('ruff', ''))}",
        f"PYLINT_CONFIG={resolve_config_path(config_dir, configs_section.get('pylint', ''))}",
        f"MYPY_CONFIG={resolve_config_path(config_dir, configs_section.get('mypy', ''))}",
        f"FLAKE8_CONFIG={resolve_config_path(config_dir, configs_section.get('flake8', ''))}",
        f"PY_INTERPRETER={interpreter}",
        f"EXCLUDE_GLOBS={','.join(configs_section.get('exclude', []))}",
    ]
    print("\n".join(lines))


def read_report(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    return Path(path).read_text()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="classify.py",
        description="Classify polylint runner output into an honest per-tool status report.",
    )
    parser.add_argument(
        "report", nargs="?", default="-", help="Path to a runner report, or - for stdin."
    )
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument(
        "--exit-code", action="store_true", help="Exit 1 when any tool is found or config-broken."
    )
    parser.add_argument(
        "--dump-config", metavar="FILE", help="Parse a .polylint.toml and print KEY=VALUE lines."
    )
    parser.add_argument(
        "--target", default="", help="Target path used for --dump-config profile matching."
    )
    parser.add_argument(
        "--profile", default="", help="Force a specific profile name for --dump-config."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.dump_config:
        dump_config(args.dump_config, args.target, args.profile)
        return 0

    text = read_report(args.report)
    reports = build_reports(text)
    output = render_json(reports) if args.format == "json" else render_markdown(reports)
    sys.stdout.write(output)

    if args.exit_code and any(report.status in ("found", "config-broken") for report in reports):
        return 1
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(newline="\n")
    sys.exit(main())
