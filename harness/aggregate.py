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


def _read_grade_data(run_dir: pathlib.Path) -> dict | None:
    """Read grade data, handling both legacy (full result) and new (manifest) grade.json formats."""
    grade_json = run_dir / "grade.json"
    grades_det = run_dir / "grades" / "deterministic" / "grade.json"
    if grade_json.exists():
        try:
            g = json.loads(grade_json.read_text())
            if "graders" in g and "paths" in g:
                # Upgrade 3: new manifest layout — read actual grade from co-located file
                det_path = run_dir / g["paths"].get("deterministic", "grades/deterministic/grade.json")
                if det_path.exists():
                    return json.loads(det_path.read_text())
                return None
            # Legacy full-grade layout
            return g
        except Exception:
            return None
    if grades_det.exists():
        try:
            return json.loads(grades_det.read_text())
        except Exception:
            return None
    return None


def aggregate_run(run_dir: pathlib.Path) -> dict | None:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return None
    run = json.loads(run_json.read_text())
    exit_code = run.get("exit_code")
    grade_data = _read_grade_data(run_dir)

    # Upgrade 4: classify runs as completed or harness_error
    has_grade = grade_data is not None
    if not has_grade or (exit_code is not None and exit_code != 0):
        run_status = "harness_error"
    else:
        run_status = None  # site derives pass/fail from passed field

    out = {
        "run_id": run["run_id"],
        "spec_id": run["spec_id"],
        "agent": run["agent"],
        "model": run["model"],
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "graded_at": None,
        "exit_code": exit_code,
        "status": run_status,
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
        "summary": None,
    }
    summary_path = run_dir / "summary.json"
    if summary_path.exists():
        try:
            out["summary"] = json.loads(summary_path.read_text())
        except Exception:
            out["summary"] = None
    if grade_data:
        out["deterministic"] = grade_data.get("deterministic", [])
        out["deterministic_score"] = grade_data.get("deterministic_score")
        out["final_score"] = grade_data.get("final_score")
        out["passed"] = grade_data.get("passed")
        out["graded_at"] = grade_data.get("graded_at")
        out["llm_judge"] = grade_data.get("llm_judge")
        # Prefer the run manifest's cost value (set by the launcher).
        if out["cost_usd"] is None:
            out["cost_usd"] = grade_data.get("cost_usd")
        if out["usage"] is None:
            out["usage"] = grade_data.get("usage")
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
        "matrix": _load_matrix(results_dir),
        "plan_usage": _load_usage(results_dir),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(doc, indent=2))
    print(f"[aggregate] {len(runs)} runs, {len(evals)} evals -> {output}")


def _load_matrix(results_dir: pathlib.Path) -> dict | None:
    matrix_path = results_dir / "eval_matrix.json"
    if not matrix_path.exists():
        return None
    try:
        matrix = json.loads(matrix_path.read_text())
        # Annotate each cell with its current pass status from `runs`.
        # The runs collection has already been computed in this same invocation;
        # cross-reference by (spec_id, agent, model, skill/condition).
        matrix_status = []
        cells = matrix.get("cells", [])
        # We can't reach `runs` from here without passing it; do a fresh lookup.
        for cell in cells:
            entry = {
                "id": cell.get("id"),
                "spec_id": cell.get("spec_id"),
                "agent": cell.get("agent"),
                "model": cell.get("model"),
                "condition": cell.get("condition"),
                "approved": bool(cell.get("approved", False)),
                "notes": cell.get("notes", ""),
                "has_passing_run": False,
                "latest_run_status": None,
            }
            # Look up the most recent run for this cell
            for run_dir in sorted((results_dir / "runs").iterdir(), reverse=True):
                if not run_dir.is_dir():
                    continue
                run_json = run_dir / "run.json"
                if not run_json.exists():
                    continue
                try:
                    rd = json.loads(run_json.read_text())
                except Exception:
                    continue
                if (
                    rd.get("spec_id") == cell.get("spec_id")
                    and rd.get("agent") == cell.get("agent")
                    and rd.get("model") == cell.get("model")
                    and rd.get("condition", "baseline") == cell.get("condition", "baseline")
                ):
                    grade_path = run_dir / "grade.json"
                    try:
                        gd = json.loads(grade_path.read_text()) if grade_path.exists() else {}
                    except Exception:
                        gd = {}
                    entry["latest_run_status"] = rd.get("status") or "completed"
                    entry["latest_run_passed"] = gd.get("passed")
                    entry["latest_run_id"] = rd.get("run_id")
                    break
            matrix_status.append(entry)
        return {
            "schema_version": matrix.get("schema_version", "1.0.0"),
            "updated_at": matrix.get("updated_at"),
            "default_max_budget_usd": matrix.get("default_max_budget_usd", 2.0),
            "default_max_turns": matrix.get("default_max_turns", 60),
            "cells": matrix_status,
        }
    except Exception:
        return None


def _load_usage(results_dir: pathlib.Path) -> dict | None:
    usage_path = results_dir / "usage.json"
    if not usage_path.exists():
        return None
    try:
        return json.loads(usage_path.read_text())
    except Exception:
        return None


if __name__ == "__main__":
    main()
