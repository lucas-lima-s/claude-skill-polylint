#!/usr/bin/env bash
set -u

POLYLINT_VERSION="0.1.0"

usage() {
  cat >&2 <<'EOF'
usage: polylint.sh <target> [--config FILE] [--profile NAME]
                    [--no-precommit] [--no-mypy] [--no-pylint] [--no-vulture] [--no-bandit]
                    [--flake8] [--black] [--isort] [--pyright] [--semgrep]
                    [--json] [--version]
EOF
  exit 2
}

[ $# -ge 1 ] || usage

if [ "$1" = "--version" ]; then
  echo "polylint $POLYLINT_VERSION"
  exit 0
fi

target="$1"; shift

run_precommit=1
run_mypy=1
run_pylint=1
run_vulture=1
run_bandit=1
run_flake8=0
run_black=0
run_isort=0
run_semgrep=0
run_pyright=0
run_json=0
opt_config=""
opt_profile=""

explicit_mypy=0
explicit_pylint=0
explicit_vulture=0
explicit_bandit=0
explicit_flake8=0
explicit_black=0
explicit_isort=0
explicit_pyright=0
explicit_semgrep=0

while [ $# -gt 0 ]; do
  arg="$1"
  case "$arg" in
    --no-precommit) run_precommit=0 ;;
    --no-mypy) run_mypy=0; explicit_mypy=1 ;;
    --no-pylint) run_pylint=0; explicit_pylint=1 ;;
    --no-vulture) run_vulture=0; explicit_vulture=1 ;;
    --no-bandit) run_bandit=0; explicit_bandit=1 ;;
    --flake8) run_flake8=1; explicit_flake8=1 ;;
    --black) run_black=1; explicit_black=1 ;;
    --isort) run_isort=1; explicit_isort=1 ;;
    --semgrep) run_semgrep=1; explicit_semgrep=1 ;;
    --pyright) run_pyright=1; explicit_pyright=1 ;;
    --json) run_json=1 ;;
    --version)
      echo "polylint $POLYLINT_VERSION"
      exit 0
      ;;
    --config)
      shift
      [ $# -ge 1 ] || usage
      opt_config="$1"
      ;;
    --profile)
      shift
      [ $# -ge 1 ] || usage
      opt_profile="$1"
      ;;
    *)
      echo "unknown flag: $arg" >&2
      usage
      ;;
  esac
  shift
done

script_dir="$(cd "$(dirname "$0")" && pwd)"
classify_py="$script_dir/scripts/classify.py"

if [ -f "$target" ] || [ -d "$target" ]; then
  case "$target" in
    /*|?:*) target_abs="$target" ;;
    *) target_abs="$(cd "$(dirname "$target")" && pwd)/$(basename "$target")" ;;
  esac
else
  target_abs="$target"
fi

PY="${POLYLINT_PY:-}"
if [ -z "$PY" ]; then
  PY="$(command -v python3 || command -v python || true)"
fi
if [ -z "$PY" ]; then
  echo "polylint: no Python interpreter found (set POLYLINT_PY, or put python3/python on PATH)" >&2
  exit 2
fi

RUN_PY="$PY"

tool_cmd() {
  local name="$1" module="$2" varname override
  varname="POLYLINT_$(printf '%s' "$name" | tr '[:lower:]' '[:upper:]')_CMD"
  override="${!varname:-}"
  if [ -n "$override" ]; then
    # shellcheck disable=SC2206
    TOOL_CMD=($override)
  else
    TOOL_CMD=("$RUN_PY" -m "$module")
  fi
}

: "${POLYLINT_CONFIG_DIR:=${XDG_CONFIG_HOME:-$HOME/.config}/polylint}"

config_file=""
if [ -n "$opt_config" ]; then
  config_file="$opt_config"
else
  dir="$target_abs"
  [ -f "$dir" ] && dir="$(dirname "$dir")"
  while [ -n "$dir" ] && [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    if [ -f "$dir/.polylint.toml" ]; then
      config_file="$dir/.polylint.toml"
      break
    fi
    parent="$(dirname "$dir")"
    [ "$parent" = "$dir" ] && break
    dir="$parent"
  done
  if [ -z "$config_file" ] && [ -f "$POLYLINT_CONFIG_DIR/polylint.toml" ]; then
    config_file="$POLYLINT_CONFIG_DIR/polylint.toml"
  fi
fi

profile_name="default"
tools_disabled=""
ruff_config=""
pylint_config=""
mypy_config=""
flake8_config=""
py_interpreter=""
exclude_globs=""

if [ -n "$config_file" ]; then
  dump_cmd=("$PY" "$classify_py" --dump-config "$config_file" --target "$target")
  [ -n "$opt_profile" ] && dump_cmd+=(--profile "$opt_profile")
  while IFS='=' read -r key value; do
    value="${value%$'\r'}"
    case "$key" in
      POLYLINT_PROFILE) [ -n "$value" ] && profile_name="$value" ;;
      POLYLINT_TOOLS_DISABLED) tools_disabled="$value" ;;
      RUFF_CONFIG) ruff_config="$value" ;;
      PYLINT_CONFIG) pylint_config="$value" ;;
      MYPY_CONFIG) mypy_config="$value" ;;
      FLAKE8_CONFIG) flake8_config="$value" ;;
      PY_INTERPRETER) py_interpreter="$value" ;;
      EXCLUDE_GLOBS) exclude_globs="$value" ;;
      *) ;;
    esac
  done < <("${dump_cmd[@]}")
fi

if [ -n "$py_interpreter" ]; then
  # Bare names like python3 must not steal a different interpreter off PATH
  # (Windows CI ships python3.exe next to the uv venv). Honor POLYLINT_PY.
  case "$py_interpreter" in
    python|python3|python3.*)
      if [ -z "${POLYLINT_PY:-}" ]; then
        resolved_interpreter="$(command -v "$py_interpreter" || true)"
        [ -n "$resolved_interpreter" ] && RUN_PY="$resolved_interpreter"
      fi
      ;;
    *)
      if [ -x "$py_interpreter" ]; then
        RUN_PY="$py_interpreter"
      else
        resolved_interpreter="$(command -v "$py_interpreter" || true)"
        [ -n "$resolved_interpreter" ] && RUN_PY="$resolved_interpreter"
      fi
      ;;
  esac
fi

shopt -s globstar nullglob 2>/dev/null || true
matches_exclude() {
  local candidate="$1" globs="$2" g
  local -a glob_arr
  IFS=',' read -ra glob_arr <<< "$globs"
  for g in "${glob_arr[@]}"; do
    [ -z "$g" ] && continue
    # shellcheck disable=SC2254
    case "$candidate" in
      $g) return 0 ;;
    esac
  done
  return 1
}

if [ -n "$exclude_globs" ] && matches_exclude "$target" "$exclude_globs"; then
  echo "# polylint: $target"
  echo "target matches an exclude glob declared in $config_file - skipping all phases"
  exit 0
fi

apply_tool_toggle() {
  local tool="$1"
  case ",$tools_disabled," in
    *",$tool,"*) return 1 ;;
    *) return 0 ;;
  esac
}

if [ -n "$tools_disabled" ]; then
  if [ "$explicit_pylint" = 0 ]; then
    if apply_tool_toggle pylint; then run_pylint=1; else run_pylint=0; fi
  fi
  if [ "$explicit_mypy" = 0 ]; then
    if apply_tool_toggle mypy; then run_mypy=1; else run_mypy=0; fi
  fi
  if [ "$explicit_vulture" = 0 ]; then
    if apply_tool_toggle vulture; then run_vulture=1; else run_vulture=0; fi
  fi
  if [ "$explicit_bandit" = 0 ]; then
    if apply_tool_toggle bandit; then run_bandit=1; else run_bandit=0; fi
  fi
  if [ "$explicit_flake8" = 0 ]; then
    if apply_tool_toggle flake8; then run_flake8=1; else run_flake8=0; fi
  fi
  if [ "$explicit_black" = 0 ]; then
    if apply_tool_toggle black; then run_black=1; else run_black=0; fi
  fi
  if [ "$explicit_isort" = 0 ]; then
    if apply_tool_toggle isort; then run_isort=1; else run_isort=0; fi
  fi
  if [ "$explicit_pyright" = 0 ]; then
    if apply_tool_toggle pyright; then run_pyright=1; else run_pyright=0; fi
  fi
  if [ "$explicit_semgrep" = 0 ]; then
    if apply_tool_toggle semgrep; then run_semgrep=1; else run_semgrep=0; fi
  fi
fi

tmp="$(mktemp -d 2>/dev/null || echo "${TEMP:-/tmp}/polylint-$$")"
mkdir -p "$tmp"
trap 'rm -rf "$tmp"' EXIT

precommit_ran=0
if [ "$run_precommit" = 1 ]; then
  cfg=""
  dir="$target_abs"
  [ -f "$dir" ] && dir="$(dirname "$dir")"
  while [ -n "$dir" ] && [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    if [ -f "$dir/.pre-commit-config.yaml" ]; then
      cfg="$dir/.pre-commit-config.yaml"
      break
    fi
    parent="$(dirname "$dir")"
    [ "$parent" = "$dir" ] && break
    dir="$parent"
  done
  if [ -n "$cfg" ]; then
    cfg_dir="$(dirname "$cfg")"
    rel_target="$(realpath --relative-to="$cfg_dir" "$target_abs" 2>/dev/null || echo "$target_abs")"
    tool_cmd precommit pre_commit
    ( cd "$cfg_dir" && "${TOOL_CMD[@]}" run --files "$rel_target" > "$tmp/precommit.out" 2>&1; echo "$?" > "$tmp/precommit.exit" )
    precommit_ran=1
  else
    echo "no .pre-commit-config.yaml found walking up from $target" > "$tmp/precommit.out"
    echo "skipped" > "$tmp/precommit.exit"
    precommit_ran=1
  fi
fi

lang="py"
case "$target" in
  *.js|*.jsx|*.ts|*.tsx|*.mjs|*.cjs) lang="js" ;;
  *.py) lang="py" ;;
esac

launch() {
  local name="$1"
  shift
  ( "$@" > "$tmp/$name.out" 2>&1; echo "$?" > "$tmp/$name.exit" ) &
}

if [ "$lang" = "py" ]; then
  tool_cmd ruff ruff
  if [ -n "$ruff_config" ]; then
    launch ruff "${TOOL_CMD[@]}" check --output-format=concise --config "$ruff_config" "$target"
  else
    launch ruff "${TOOL_CMD[@]}" check --output-format=concise "$target"
  fi

  if [ "$run_pylint" = 1 ]; then
    tool_cmd pylint pylint
    if [ -n "$pylint_config" ]; then
      launch pylint "${TOOL_CMD[@]}" "--rcfile=$pylint_config" "$target"
    else
      launch pylint "${TOOL_CMD[@]}" "$target"
    fi
  fi
  if [ "$run_mypy" = 1 ]; then
    tool_cmd mypy mypy
    if [ -n "$mypy_config" ]; then
      launch mypy "${TOOL_CMD[@]}" --config-file "$mypy_config" "$target"
    else
      launch mypy "${TOOL_CMD[@]}" --follow-imports=skip "$target"
    fi
  fi
  if [ "$run_vulture" = 1 ]; then
    tool_cmd vulture vulture
    launch vulture "${TOOL_CMD[@]}" "$target"
  fi
  if [ "$run_bandit" = 1 ]; then
    tool_cmd bandit bandit
    if [ -d "$target" ]; then
      launch bandit "${TOOL_CMD[@]}" -r -q "$target"
    else
      launch bandit "${TOOL_CMD[@]}" -q "$target"
    fi
  fi
  if [ "$run_flake8" = 1 ]; then
    tool_cmd flake8 flake8
    if [ -n "$flake8_config" ]; then
      launch flake8 "${TOOL_CMD[@]}" --config "$flake8_config" "$target"
    else
      launch flake8 "${TOOL_CMD[@]}" "$target"
    fi
  fi
  if [ "$run_black" = 1 ]; then
    tool_cmd black black
    launch black "${TOOL_CMD[@]}" --check "$target"
  fi
  if [ "$run_isort" = 1 ]; then
    tool_cmd isort isort
    launch isort "${TOOL_CMD[@]}" --check "$target"
  fi
  if [ "$run_semgrep" = 1 ]; then
    if "$RUN_PY" -m semgrep --version >/dev/null 2>&1; then
      launch semgrep "$RUN_PY" -m semgrep --config p/python --quiet --error --timeout 60 "$target"
    elif command -v semgrep >/dev/null 2>&1; then
      launch semgrep semgrep --config p/python --quiet --error --timeout 60 "$target"
    elif command -v wsl.exe >/dev/null 2>&1 && wsl.exe -e bash -lic 'command -v semgrep' >/dev/null 2>&1; then
      win_target="$target"
      command -v cygpath >/dev/null 2>&1 && win_target="$(cygpath -w "$target")"
      wsl_target="$(wsl.exe -e wslpath -a "$win_target" 2>/dev/null | tr -d '\r\n')"
      if [ -n "$wsl_target" ]; then
        launch semgrep wsl.exe -e bash -lic "semgrep --config p/python --quiet --error --timeout 60 '$wsl_target'"
      else
        printf 'semgrep (WSL): failed to convert %s to a WSL path\n' "$win_target" > "$tmp/semgrep.out"
        echo "skipped" > "$tmp/semgrep.exit"
      fi
    else
      {
        echo "semgrep not found. Install options:"
        echo "  1. \"\$POLYLINT_PY\" -m pip install semgrep"
        echo "  2. WSL: wsl -e pipx install semgrep (once installed, --semgrep routes through it automatically)"
        echo "  3. Docker: docker run --rm -v \"\${PWD}:/src\" returntocorp/semgrep:latest --config p/python /src"
      } > "$tmp/semgrep.out"
      echo "skipped" > "$tmp/semgrep.exit"
    fi
  fi
  if [ "$run_pyright" = 1 ]; then
    tool_cmd pyright pyright
    launch pyright "${TOOL_CMD[@]}" "$target"
  fi
fi

if [ "$lang" = "js" ]; then
  eslint_root=""
  d="$(cd "$(dirname "$target")" && pwd)"
  while [ -n "$d" ] && [ "$d" != "/" ]; do
    if [ -f "$d/package.json" ] && { [ -f "$d/.eslintrc.js" ] || [ -f "$d/.eslintrc.json" ] || [ -f "$d/.eslintrc.yml" ] || [ -f "$d/eslint.config.js" ] || [ -f "$d/eslint.config.mjs" ] || [ -f "$d/eslint.config.cjs" ] || [ -f "$d/eslint.config.ts" ]; }; then
      eslint_root="$d"
      break
    fi
    parent="$(dirname "$d")"
    [ "$parent" = "$d" ] && break
    d="$parent"
  done

  if [ -n "$eslint_root" ]; then
    rel="$(realpath --relative-to="$eslint_root" "$(cd "$(dirname "$target")" && pwd)/$(basename "$target")" 2>/dev/null || echo "$target")"
    launch eslint bash -c "cd '$eslint_root' && npx --no-install eslint '$rel'"
    launch prettier bash -c "cd '$eslint_root' && npx --no-install prettier --check '$rel'"
  elif [ -n "${POLYLINT_JS_DIR:-}" ]; then
    launch eslint bash -c "cd '$POLYLINT_JS_DIR' && npx --no-install eslint '$target'"
    launch prettier bash -c "cd '$POLYLINT_JS_DIR' && npx --no-install prettier --check '$target'"
  else
    printf 'no package.json + eslint config found walking up from %s, and POLYLINT_JS_DIR is not set\n' "$target" > "$tmp/eslint.out"
    echo "tool-missing" > "$tmp/eslint.exit"
    printf 'no package.json + prettier setup found walking up from %s, and POLYLINT_JS_DIR is not set\n' "$target" > "$tmp/prettier.out"
    echo "tool-missing" > "$tmp/prettier.exit"
  fi
fi

wait

emit() {
  local name="$1" out ex rc
  out="$tmp/$name.out"
  ex="$tmp/$name.exit"
  [ -f "$out" ] || return 0
  rc="$(cat "$ex" 2>/dev/null || echo '?')"
  printf '\n===== %s (exit=%s) =====\n' "$name" "$rc"
  if [ -s "$out" ]; then cat "$out"; else echo "(no output)"; fi
}

print_report() {
  echo "# polylint: $target"
  echo "profile: $profile_name"
  echo "lang: $lang"
  [ "$precommit_ran" = 1 ] && emit precommit
  if [ "$lang" = "py" ]; then
    emit ruff
    [ "$run_pylint" = 1 ] && emit pylint
    [ "$run_mypy" = 1 ] && emit mypy
    [ "$run_vulture" = 1 ] && emit vulture
    [ "$run_bandit" = 1 ] && emit bandit
    [ "$run_flake8" = 1 ] && emit flake8
    [ "$run_black" = 1 ] && emit black
    [ "$run_isort" = 1 ] && emit isort
    [ "$run_semgrep" = 1 ] && emit semgrep
    [ "$run_pyright" = 1 ] && emit pyright
  fi
  if [ "$lang" = "js" ]; then
    emit eslint
    emit prettier
  fi
}

if [ "$run_json" = 1 ]; then
  print_report | "$PY" "$classify_py" --format json
else
  print_report
fi

exit 0
