#!/usr/bin/env python3
"""Agent Evals — nightly eval dispatcher.

Reads results/eval_matrix.json + results.json + results/usage.json and launches
new runs for any (spec, agent, model) cell that:
  - has approved=true
  - has no passing run on record
  - has a CLI that is on PATH
  - is within budget (per-lane remaining > 50% of weekly quota) when usage data exists

Run from the project root:
    python harness/nightly_dispatch.py [--dry-run]

In dry-run mode, prints the plan without invoking any CLI.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any


PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
MATRIX_PATH = PROJECT_ROOT / "results" / "eval_matrix.json"
RESULTS_PATH = PROJECT_ROOT / "results" / "results.json"
USAGE_PATH = PROJECT_ROOT / "results" / "usage.json"

# Lane-name -> per-lane minimum remaining percentage required to launch.
# 50% means "leave half the weekly quota unused". Tune per project.
LANE_MIN_REMAINING_PCT = {
    "claude": 50.0,
    "codex": 50.0,
    "cursor": 50.0,
    "minimax": 50.0,
}


def _lane_for_agent(agent: str) -> str:
    # Mapping from harness agent name to usage-dashboard lane id.
    return {
        "claude-code": "claude",
        "cursor-agent": "cursor",
        "codex": "codex",
        "coder-codex": "codex",
        "hermes-cli": "minimax",
    }.get(agent, agent)


def _has_passing_run(results: dict, spec_id: str, agent: str, model: str, condition: str) -> bool:
    for run in results.get("runs", []):
        if (
            run.get("spec_id") == spec_id
            and run.get("agent") == agent
            and run.get("model") == model
            and run.get("skill") == condition
            and run.get("passed") is True
        ):
            return True
    return False


def _lane_headroom_pct(usage: dict | None, lane: str) -> float | None:
    """Return remaining% for a lane, or None if unknown."""
    if not usage:
        return None
    providers = usage.get("providers") or []
    for p in providers:
        if p.get("id") == lane:
            up = p.get("usagePeriod") or {}
            return up.get("remainingPercent")
    return None


def _cli_on_path(agent: str) -> bool:
    bin_ = {
        "claude-code": "claude",
        "cursor-agent": "cursor-agent",
        "codex": "codex",
        "coder-codex": "codex",
        "hermes-cli": "hermes",
    }.get(agent, agent)
    return subprocess.run(["which", bin_], capture_output=True).returncode == 0


def _launch(cell: dict) -> dict:
    """Launch one eval via harness/launch_eval.sh. Returns a small report dict."""
    spec_yaml = f"evals/{cell['spec_id']}.yaml"
    run_id = f"{cell['spec_id']}-{cell['agent']}-nightly-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    cmd = [
        "bash",
        "harness/launch_eval.sh",
        spec_yaml,
        run_id,
        cell.get("condition", "baseline"),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_ROOT)
    return {
        "run_id": run_id,
        "spec_id": cell["spec_id"],
        "agent": cell["agent"],
        "model": cell["model"],
        "condition": cell.get("condition", "baseline"),
        "exit_code": proc.returncode,
        "stdout_tail": proc.stdout[-500:] if proc.stdout else "",
        "stderr_tail": proc.stderr[-500:] if proc.stderr else "",
    }


def plan(matrix: dict, results: dict, usage: dict | None, dry_run: bool) -> list[dict]:
    decisions: list[dict] = []
    for cell in matrix.get("cells", []):
        decision = {
            "cell_id": cell.get("id"),
            "spec_id": cell.get("spec_id"),
            "agent": cell.get("agent"),
            "model": cell.get("model"),
            "condition": cell.get("condition"),
            "approved": cell.get("approved", False),
            "already_passing": _has_passing_run(results, cell["spec_id"], cell["agent"], cell["model"], cell.get("condition", "baseline")),
            "lane": _lane_for_agent(cell["agent"]),
            "lane_remaining_pct": _lane_headroom_pct(usage, _lane_for_agent(cell["agent"])),
            "cli_on_path": _cli_on_path(cell["agent"]),
            "will_launch": False,
            "skip_reason": None,
        }
        if not decision["approved"]:
            decision["skip_reason"] = "not approved in matrix"
        elif decision["already_passing"]:
            decision["skip_reason"] = "already has a passing run"
        elif not decision["cli_on_path"]:
            decision["skip_reason"] = f"CLI '{cell['agent']}' not on PATH"
        else:
            lane = decision["lane"]
            min_pct = LANE_MIN_REMAINING_PCT.get(lane, 50.0)
            remaining = decision["lane_remaining_pct"]
            if remaining is not None and remaining < min_pct:
                decision["skip_reason"] = (
                    f"lane '{lane}' has only {remaining:.1f}% remaining (< {min_pct:.0f}% threshold)"
                )
            else:
                decision["will_launch"] = True
        decisions.append(decision)
    return decisions


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="Print the plan without launching any CLI.")
    ap.add_argument("--matrix", default=str(MATRIX_PATH))
    ap.add_argument("--results", default=str(RESULTS_PATH))
    ap.add_argument("--usage", default=str(USAGE_PATH))
    args = ap.parse_args()

    matrix = json.loads(pathlib.Path(args.matrix).read_text())
    results = json.loads(pathlib.Path(args.results).read_text()) if pathlib.Path(args.results).exists() else {"runs": []}
    usage = json.loads(pathlib.Path(args.usage).read_text()) if pathlib.Path(args.usage).exists() else None

    decisions = plan(matrix, results, usage, dry_run=args.dry_run)

    if args.dry_run:
        print(json.dumps({"mode": "dry-run", "decisions": decisions}, indent=2))
        return

    launched = []
    for d in decisions:
        if d["will_launch"]:
            cell = next(c for c in matrix["cells"] if c.get("id") == d["cell_id"])
            launched.append(_launch(cell))
            print(f"launched {cell['id']} exit={launched[-1]['exit_code']}")
        else:
            print(f"skip    {d['cell_id']:60s} {d['skip_reason']}")

    print(json.dumps({"mode": "live", "decisions": decisions, "launched": launched}, indent=2))


if __name__ == "__main__":
    main()