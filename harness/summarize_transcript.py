#!/usr/bin/env python3
"""Agent Evals — transcript summarizer.

Reads a run's stdout.txt and produces a structured issue summary. The summary
is written to <run-dir>/summary.json. The aggregator picks it up and the
published site renders it as a "What we observed" panel on the run detail page.

This summarizer is a heuristic, not an LLM judge — it extracts concrete signals
the agent left in its transcript (commands run, errors encountered, warnings
emitted) and produces a faithful summary without inventing issues. LLM-grade
narrative summaries are intentionally not in scope; the harness should never
fabricate issues to make a run look more or less successful.

Usage:
    python harness/summarize_transcript.py --run results/runs/run-002-led-blinky-cursor
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


SIGNAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("installed_tool", re.compile(r"\b(?:apt-get install|pip install|npm install|brew install)\b", re.IGNORECASE)),
    ("kicad_crash", re.compile(r"\b(?:SIGSEGV|Segmentation fault|kicad-cli.*(?:crash|segfault))\b", re.IGNORECASE)),
    ("uuid_problem", re.compile(r"\b(?:UUID|uuid|placeholder).{0,80}(?:crash|null-deref|parser|invalid)", re.IGNORECASE)),
    ("erc_failure", re.compile(r"\bERC\b.{0,80}(?:fail|violation|error)", re.IGNORECASE)),
    ("drc_failure", re.compile(r"\bDRC\b.{0,80}(?:fail|violation|error)", re.IGNORECASE)),
    ("gerber_export_failure", re.compile(r"\b(?:gerber|export).{0,80}(?:fail|error|cannot)", re.IGNORECASE)),
    ("budget_exhausted", re.compile(r"(?:Exceeded USD budget|maximum budget|reached max budget)", re.IGNORECASE)),
    ("session_limit", re.compile(r"(?:hit your session limit|session.*limit.*reset)", re.IGNORECASE)),
    ("iteration_budget", re.compile(r"(?:Iteration budget reached|turns? reached|tool calls? reached)", re.IGNORECASE)),
    ("interrupted", re.compile(r"\b(?:interrupted|killed|timeout|timed out)\b", re.IGNORECASE)),
    ("connection_lost", re.compile(r"(?:network.*(?:unreachable|lost)|connection.*(?:reset|closed))", re.IGNORECASE)),
    ("missing_component", re.compile(r"(?:missing from stock|not (?:found|in).{0,30}(?:library|footprint|symbol))", re.IGNORECASE)),
    ("substituted_component", re.compile(r"\b(?:substitut|equivalent).{0,80}(?:footprint|part|symbol|stock)", re.IGNORECASE)),
    ("library_install", re.compile(r"(?:apt.{0,30}install|installed.{0,40}(?:kicad|ngspice|freecad))", re.IGNORECASE)),
    ("wrote_files", re.compile(r"(?:Wrote |wrote |emitted )(?:[/\w.\-]+\.(?:kicad_(?:sch|pcb|pro)|csv|gbr|gbl|gtl|gts|gbs|gto|gbo|gtp|gbp|gm1|drl|json))", re.IGNORECASE)),
    ("ran_validation", re.compile(r"(?:kicad-cli|gerber|ERC|DRC).{0,40}(?:exit|status)\s*[1-9]", re.IGNORECASE)),
    ("self_reported_score", re.compile(r"(?:27 errors|130 ERC|136 DRC|\d+\s*(?:ERC|DRC|violations?))", re.IGNORECASE)),
    ("gave_up", re.compile(r"(?:resume this session|want me to resume|ran out of|out of tool calls)", re.IGNORECASE)),
]


def extract_signals(transcript: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for label, pattern in SIGNAL_PATTERNS:
        for match in pattern.finditer(transcript):
            start = max(match.start() - 60, 0)
            end = min(match.end() + 60, len(transcript))
            context = transcript[start:end].replace("\n", " ").strip()
            found.setdefault(label, []).append(context)
    return {k: v[:3] for k, v in found.items()}


def build_summary(run_dir: pathlib.Path) -> dict[str, Any]:
    run_json_path = run_dir / "run.json"
    run_meta: dict[str, Any] = {}
    if run_json_path.exists():
        try:
            run_meta = json.loads(run_json_path.read_text())
        except Exception:
            run_meta = {}

    stdout_path = run_dir / "stdout.txt"
    transcript = stdout_path.read_text(errors="replace") if stdout_path.exists() else ""

    signals = extract_signals(transcript)
    issues = []
    if signals.get("budget_exhausted"):
        issues.append("run was cut short by the $2 budget cap")
    if signals.get("session_limit"):
        issues.append("CLI session limit was hit before the run could start")
    if signals.get("iteration_budget"):
        issues.append("agent ran out of tool turns before finishing")
    if signals.get("kicad_crash"):
        issues.append("kicad-cli crashed mid-run")
    if signals.get("uuid_problem"):
        issues.append("placeholder UUIDs triggered kicad-cli parser failure")
    if signals.get("erc_failure"):
        issues.append("ERC reported violations in the schematic")
    if signals.get("drc_failure"):
        issues.append("DRC reported violations in the PCB")
    if signals.get("gerber_export_failure"):
        issues.append("gerber export did not complete cleanly")
    if signals.get("connection_lost"):
        issues.append("network or connection error interrupted the run")
    if signals.get("missing_component"):
        issues.append("a required component was missing from the stock KiCad libraries")
    if signals.get("substituted_component"):
        issues.append("a component was substituted because the spec-required part was unavailable")
    if signals.get("gave_up"):
        issues.append("agent self-reported being unable to finish within the tool budget")
    if signals.get("ran_validation") and not issues:
        issues.append("validation commands ran with non-zero exit codes")

    actions = []
    if signals.get("installed_tool"):
        actions.append("installed missing tooling")
    if signals.get("library_install"):
        actions.append("installed KiCad or related libraries")
    if signals.get("wrote_files"):
        actions.append("wrote primary KiCad project files")

    finished_files = signals.get("wrote_files", [])
    if finished_files:
        actions.append(f"produced at least {len(finished_files)} KiCad output file(s)")

    observations = []
    for n in signals.get("self_reported_score", []):
        observations.append(n.strip())

    if not issues and not actions:
        return {
            "run_id": run_meta.get("run_id", run_dir.name),
            "agent": run_meta.get("agent", "unknown"),
            "model": run_meta.get("model", "unknown"),
            "duration_estimate": None,
            "transcript_size_bytes": len(transcript.encode("utf-8")),
            "verdict": "no notable signals extracted from transcript",
            "actions": [],
            "issues": [],
            "observations": [],
        }

    return {
        "run_id": run_meta.get("run_id", run_dir.name),
        "agent": run_meta.get("agent", "unknown"),
        "model": run_meta.get("model", "unknown"),
        "duration_estimate": _duration_label(run_meta),
        "transcript_size_bytes": len(transcript.encode("utf-8")),
        "verdict": _summarize_verdict(issues, actions),
        "actions": actions,
        "issues": issues,
        "observations": observations,
        "evidence": {k: v for k, v in signals.items() if k not in {"wrote_files"}},
    }


def _duration_label(run_meta: dict[str, Any]) -> str | None:
    start = run_meta.get("started_at")
    end = run_meta.get("finished_at")
    if not (start and end):
        return None
    try:
        from datetime import datetime
        s = datetime.fromisoformat(start.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end.replace("Z", "+00:00"))
        delta = (e - s).total_seconds()
        if delta < 0:
            return None
        if delta < 60:
            return f"{int(delta)} s"
        if delta < 3600:
            return f"{int(delta // 60)}m {int(delta % 60)}s"
        return f"{int(delta // 3600)}h {int((delta % 3600) // 60)}m"
    except Exception:
        return None


def _summarize_verdict(issues: list[str], actions: list[str]) -> str:
    if issues and "ran out of tool turns before finishing" in issues and not actions:
        return "agent self-reported incomplete; produced no primary deliverables"
    if any("session limit" in s for s in issues):
        return "session limit hit before run could start"
    if "agent self-reported being unable to finish within the tool budget" in issues:
        return "agent ran out of tool turns; partial artifacts at best"
    if "kicad-cli crashed mid-run" in issues:
        return "kicad-cli crashed mid-run"
    if "placeholder UUIDs triggered kicad-cli parser failure" in issues:
        return "schematic UUID format tripped kicad-cli parser"
    if "ERC reported violations in the schematic" in issues and "DRC reported violations in the PCB" in issues:
        return "completed artifacts but ERC and DRC both report violations"
    if "ERC reported violations in the schematic" in issues:
        return "ERC flagged violations in the schematic"
    if "DRC reported violations in the PCB" in issues:
        return "DRC flagged violations in the PCB"
    if actions and not issues:
        return "no notable issues extracted from transcript"
    return "see issues below"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="Path to the run directory.")
    ap.add_argument("--output", default=None, help="Override output path; defaults to <run>/summary.json.")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    if not run_dir.exists():
        sys.exit(f"Run directory does not exist: {run_dir}")
    out_path = pathlib.Path(args.output).resolve() if args.output else (run_dir / "summary.json")
    summary = build_summary(run_dir)
    out_path.write_text(json.dumps(summary, indent=2))
    print(json.dumps({"run_id": summary["run_id"], "summary_path": str(out_path), "issues": len(summary["issues"]), "actions": len(summary["actions"])}))


if __name__ == "__main__":
    main()
