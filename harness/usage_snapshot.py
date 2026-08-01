#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
"""
Agent Evals — usage_snapshot.py

Capture a plan-level usage snapshot for the four lanes (claude, codex, cursor,
minimax) by shelling out to the usage-dashboard's usage-cli.js. The output
schema is preserved so the snapshot is interchangeable with the dashboard's
own summary; only an `updated_at` field and a per-lane `_available` flag are
added for the agent-evals site.

Usage:
  python harness/usage_snapshot.py                  # write to results/usage.json
  python harness/usage_snapshot.py --out /tmp/x.json
  python harness/usage_snapshot.py --print         # JSON to stdout
  python harness/usage_snapshot.py --dashboard-dir /home/ragiton/projects/usage-dashboard

The CLI never raises on a per-lane failure — every lane degrades to an
"unavailable" entry with the dashboard's `reason` field, so the site can
render a single failure path even if one of the four providers is down.
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys, datetime
from typing import Any

HARNESS = pathlib.Path(__file__).resolve().parent
PROJECT = HARNESS.parent
DEFAULT_DASHBOARD = pathlib.Path("/home/ragiton/projects/usage-dashboard")
DEFAULT_OUT = PROJECT / "results" / "usage.json"


def _run_dashboard(dashboard_dir: pathlib.Path, timeout: float = 60.0) -> dict:
    cli = dashboard_dir / "usage-cli.js"
    if not cli.exists():
        return {"error": f"dashboard CLI not found at {cli}", "providers": []}
    try:
        proc = subprocess.run(
            ["node", str(cli)],
            cwd=str(dashboard_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": "usage-cli.js timed out", "providers": []}
    except Exception as e:
        return {"error": f"usage-cli.js failed to start: {e}", "providers": []}
    if proc.returncode != 0:
        return {
            "error": f"usage-cli.js exited {proc.returncode}",
            "stderr": (proc.stderr or "")[:400],
            "providers": [],
        }
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"usage-cli.js emitted non-JSON output: {e}", "providers": []}


def _normalize_providers(summary: dict) -> list[dict]:
    """Pass-through with a stable ordering and a per-lane `_available` flag.

    The dashboard already produces a clean public projection; we just add a
    normalized `available` boolean and clamp percent values to [0, 100].
    """
    out: list[dict] = []
    for p in summary.get("providers", []) or []:
        period = p.get("usagePeriod") or {}
        used = period.get("usedPercent")
        remaining = period.get("remainingPercent")
        # Clamp & coerce
        if isinstance(used, (int, float)) and used is not None:
            used = max(0, min(100, used))
        if isinstance(remaining, (int, float)) and remaining is not None:
            remaining = max(0, min(100, remaining))
        if used is None and remaining is None:
            available = False
        else:
            available = (p.get("status") == "live") and (used is not None or remaining is not None)
        out.append({
            "id": p.get("id"),
            "displayName": p.get("displayName"),
            "status": p.get("status"),
            "source": p.get("source"),
            "reason": p.get("reason"),
            "available": available,
            "usagePeriod": {
                "type": period.get("type"),
                "label": period.get("label"),
                "usedPercent": used,
                "remainingPercent": remaining,
                "resetAt": period.get("resetAt"),
            },
            "weekly": p.get("weekly"),
        })
    # Stable order so the site renders consistently.
    lane_order = {"claude": 0, "codex": 1, "cursor": 2, "minimax": 3}
    out.sort(key=lambda p: lane_order.get(p.get("id") or "", 99))
    return out


def build_snapshot(dashboard_dir: pathlib.Path = DEFAULT_DASHBOARD) -> dict:
    summary = _run_dashboard(dashboard_dir)
    providers = _normalize_providers(summary)
    snap = {
        "schema_version": "1.0.0",
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dashboard_generated_at": summary.get("generatedAt"),
        "dashboard_schema_version": summary.get("schemaVersion"),
        "lanes": providers,
        "source": {
            "dashboard_cli": str((dashboard_dir / "usage-cli.js").resolve()),
            "dashboard_repo": str(dashboard_dir),
        },
    }
    if "error" in summary:
        snap["dashboard_error"] = summary["error"]
    if "stderr" in summary:
        snap["dashboard_stderr"] = summary["stderr"]
    return snap


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT),
                    help="output JSON path (default: results/usage.json)")
    ap.add_argument("--dashboard-dir", default=str(DEFAULT_DASHBOARD))
    ap.add_argument("--print", action="store_true",
                    help="write JSON to stdout instead of file")
    args = ap.parse_args()
    snap = build_snapshot(pathlib.Path(args.dashboard_dir).expanduser().resolve())
    text = json.dumps(snap, indent=2)
    if args.print:
        sys.stdout.write(text + "\n")
        return 0
    out = pathlib.Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    available = sum(1 for lane in snap["lanes"] if lane.get("available"))
    total = len(snap["lanes"])
    print(f"[usage-snapshot] {available}/{total} lanes live -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
