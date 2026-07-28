#!/usr/bin/env bash
# Dispatch the common harness commands while keeping arbitrary CLI commands
# available for ad-hoc KiCad/ngspice/FreeCAD checks.
set -Eeuo pipefail

HARNESS_DIR="${HARNESS_DIR:-/opt/agent-evals/harness}"

usage() {
    cat <<'EOF'
Agent Evals container

Commands:
  verify                  print tool versions and check harness imports
  runner.py [args...]     run harness/runner.py
  grader.py [args...]     run harness/grader.py
  cross_grade.py [args...] run harness/cross_grade.py
  aggregate.py [args...]  run harness/aggregate.py
  <command> [args...]     execute an arbitrary command in the image

Examples:
  docker run --rm agent-evals:9.0.8 verify
  docker run --rm -v "$PWD:/workspace" agent-evals:9.0.8 \
      runner.py --spec /workspace/evals/01-led-blinky-minimal.yaml \
      --agent claude-code --dry-run
EOF
}

print_version() {
    local label="$1"
    shift
    local output
    if output=$("$@" --version 2>&1); then
        printf '%s: %s\n' "$label" "$output"
    else
        # Some Debian CLI builds expose only --help. Running it still proves
        # that the executable and its shared libraries are callable.
        output=$("$@" --help 2>&1)
        printf '%s: version flag unavailable; help probe: %s\n' \
            "$label" "${output%%$'\n'*}"
    fi
}

print_kicad_version() {
    local output
    if output=$(kicad-cli version 2>&1); then
        printf 'kicad-cli: %s\n' "$output"
    else
        print_version "kicad-cli" kicad-cli
    fi
}

verify() {
    printf 'agent-evals toolchain verification\n'
    print_kicad_version
    print_version "ngspice" ngspice
    print_version "freecad-cli" freecad-cli
    print_version "python3" python3
    printf 'bash: %s\n' "$(bash --version | head -n 1)"

    python3 - <<'PY'
import jinja2
import yaml
print(f"python modules: PyYAML {yaml.__version__}, Jinja2 {jinja2.__version__}")
PY

    for script in runner.py grader.py cross_grade.py aggregate.py; do
        python3 "$HARNESS_DIR/$script" --help >/dev/null
    done
    printf 'harness: runner.py, grader.py, cross_grade.py, aggregate.py callable\n'
}

command="${1:-help}"
case "$command" in
    help|-h|--help)
        usage
        ;;
    verify)
        verify
        ;;
    runner.py|runner)
        shift
        exec python3 "$HARNESS_DIR/runner.py" "$@"
        ;;
    grader.py|grader)
        shift
        exec python3 "$HARNESS_DIR/grader.py" "$@"
        ;;
    cross_grade.py|cross-grade)
        shift
        exec python3 "$HARNESS_DIR/cross_grade.py" "$@"
        ;;
    aggregate.py|aggregate)
        shift
        exec python3 "$HARNESS_DIR/aggregate.py" "$@"
        ;;
    *)
        exec "$@"
        ;;
esac
