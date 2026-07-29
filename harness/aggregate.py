# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
#!/usr/bin/env python3
"""
Agent Evals — aggregate.py

Walks results/runs/*/ and rebuilds results.json from grade.json + cross_grade*.json.
The site reads results.json; runner/grader write per-run files; aggregate splices
them into the single source of truth.

Usage:
  python harness/aggregate.py
  python harness/aggregate.py --results-dir results
"""
from __future__ import annotations
import argparse, json, pathlib, datetime, sys
import yaml


def find_specs(evals_dir: pathlib.Path) -> list[dict]:
    """Load one canonical definition per eval id.

    Early scaffold files were numbered (``01-...yaml``) and later richer
    definitions were added without the numeric prefix.  Both may exist in a
    checkout, but the site must not render duplicate catalog entries.  Prefer
    the unnumbered definition, then the richer prompt/requirements payload.
    """
    candidates: dict[str, list[tuple[pathlib.Path, dict]]] = {}
    for f in sorted(evals_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text()) or {}
            spec_id = data["id"]
            candidates.setdefault(spec_id, []).append((f, data))
        except Exception as e:
            print(f"warn: failed to parse {f}: {e}", file=sys.stderr)

    out = []
    for spec_id, entries in sorted(candidates.items()):
        def rank(item):
            f, data = item
            numbered = bool(f.name[:1].isdigit())
            richness = len(data.get("prompt", "")) + 100 * len(data.get("engineering_requirements", []))
            return (numbered, -richness, f.name)
        f, data = sorted(entries, key=rank)[0]
        out.append({
            "id": spec_id,
            "title": data.get("title"),
            "description": data.get("description"),
            "difficulty": data.get("difficulty"),
            "estimated_minutes": data.get("estimated_minutes"),
            "category": data.get("category"),
            "grading": data.get("grading"),
            "source_path": str(f.relative_to(evals_dir.parent)),
        })
    return out


def aggregate_run(run_dir: pathlib.Path) -> dict | None:
    run_json = run_dir / "run.json"
    grade_json = run_dir / "grade.json"
    if not run_json.exists():
        return None
    run = json.loads(run_json.read_text())
    out = {
        "run_id": run["run_id"],
        "spec_id": run["spec_id"],
        "agent": run["agent"],
        "model": run["model"],
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "graded_at": None,
        "exit_code": run.get("exit_code"),
        "deterministic": [],
        "deterministic_score": None,
        "final_score": None,
        "passed": None,
        "llm_judge": None,
        "cross_grades": [],
        "cost_usd": run.get("cost_usd"),
        "usage": run.get("usage"),
        "skill": run.get("condition"),
        "max_budget_usd": run.get("max_budget_usd"),
    }
    if grade_json.exists():
        g = json.loads(grade_json.read_text())
        out["deterministic"] = g.get("deterministic", [])
        out["deterministic_score"] = g.get("deterministic_score")
        out["final_score"] = g.get("final_score")
        out["passed"] = g.get("passed")
        out["graded_at"] = g.get("graded_at")
        out["llm_judge"] = g.get("llm_judge")
        # The grader may also have computed a cost from the envelope; prefer
        # the run manifest's value (it's set by the launcher).
        if out["cost_usd"] is None:
            out["cost_usd"] = g.get("cost_usd")
        if out["usage"] is None:
            out["usage"] = g.get("usage")
    for cross_file in sorted(run_dir.glob("cross_grade_*.json")):
        c = json.loads(cross_file.read_text())
        out["cross_grades"].append({
            "agent": c.get("agent"),
            "model": c.get("model"),
            "exit_code": c.get("exit_code"),
            "graded_at": c.get("graded_at"),
            "verdict_snippet": (c.get("stdout") or "")[:500],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--output", default="results/results.json")
    args = ap.parse_args()

    project_root = pathlib.Path(__file__).resolve().parent.parent
    results_dir = (project_root / args.results_dir).resolve()
    evals_dir = (project_root / "evals").resolve()
    output = (project_root / args.output).resolve()

    evals = find_specs(evals_dir)
    runs = []
    runs_dir = results_dir / "runs"
    if runs_dir.exists():
        for run_dir in sorted(runs_dir.iterdir()):
            if run_dir.is_dir():
                a = aggregate_run(run_dir)
                if a:
                    runs.append(a)

    doc = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "schema_version": "1.0.0",
        "evals": evals,
        "runs": runs,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2))
    print(f"[aggregate] {len(runs)} runs, {len(evals)} evals -> {output}")


if __name__ == "__main__":
    main()
