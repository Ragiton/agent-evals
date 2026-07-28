# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
#!/usr/bin/env bash
# Launch one bounded Claude Code engineering eval in an isolated workspace.
# Usage: launch_eval.sh <spec.yaml> <run-id> [skill]
set -euo pipefail

SPEC=${1:?spec path required}
RUN_ID=${2:?run id required}
SKILL=${3:-baseline}
ROOT=/home/ragiton/projects/agent-evals
RUN_DIR="$ROOT/results/runs/$RUN_ID"
WORKSPACE="$RUN_DIR/workspace"
mkdir -p "$WORKSPACE"

python3 - "$SPEC" "$RUN_ID" "$RUN_DIR" "$WORKSPACE" "$SKILL" <<'PY'
import json, pathlib, sys, yaml, datetime
spec_path, run_id, run_dir, workspace, skill = sys.argv[1:]
spec = yaml.safe_load(pathlib.Path(spec_path).read_text())
manifest = {
    "run_id": run_id,
    "spec_id": spec["id"],
    "agent": "claude-code",
    "model": "claude-sonnet-4-6",
    "condition": skill,
    "spec_path": str(pathlib.Path(spec_path).resolve()),
    "workspace": str(pathlib.Path(workspace).resolve()),
    "output_dir": str(pathlib.Path(run_dir).resolve()),
    "max_budget_usd": 2.0,
    "max_turns": 80,
    "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "prompt_chars": len(spec.get("prompt", "")),
}
pathlib.Path(run_dir, "run.json").write_text(json.dumps(manifest, indent=2))
pathlib.Path(run_dir, "prompt.txt").write_text(spec.get("prompt", ""))
PY

# The spec prompt is the contract. Skill conditions are supplied only via PATH.
if [[ "$SKILL" == "mash-kicad-skills" ]]; then
  export PATH="/tmp/kicad-skills-venv/bin:$PATH"
fi

cd "$WORKSPACE"
set +e
claude -p \
  --model claude-sonnet-4-6 \
  --permission-mode bypassPermissions \
  --max-budget-usd 2.0 \
  --max-turns 80 \
  < "$RUN_DIR/prompt.txt" \
  > "$RUN_DIR/stdout.txt" \
  2> "$RUN_DIR/stderr.txt"
RC=$?
set -e

python3 - "$RUN_DIR" "$RC" <<'PY'
import json, pathlib, sys, datetime
run_dir, rc = sys.argv[1], int(sys.argv[2])
p = pathlib.Path(run_dir) / "run.json"
d = json.loads(p.read_text())
d.update({
    "exit_code": rc,
    "finished_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "stdout_bytes": (pathlib.Path(run_dir) / "stdout.txt").stat().st_size,
    "stderr_bytes": (pathlib.Path(run_dir) / "stderr.txt").stat().st_size,
})
p.write_text(json.dumps(d, indent=2))
print(json.dumps({"run_id": d["run_id"], "exit_code": rc, "workspace": d["workspace"]}))
PY
exit "$RC"
