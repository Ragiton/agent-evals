#!/usr/bin/env python3
"""
Agent Evals — grader.py

Runs deterministic checks on a captured run, then optionally invokes an LLM judge.
Writes results.json into the run directory.

Usage:
  python harness/grader.py --run results/runs/<run-id>/
  python harness/grader.py --run results/runs/<run-id>/ --no-llm
  python harness/grader.py --run results/runs/<run-id>/ --cross-grade --agent codex --model gpt-5.6-luna
"""
from __future__ import annotations
import argparse, json, os, pathlib, subprocess, sys, datetime, re

# Map spec placeholder tokens to actual filenames in the workspace
SUBSTITUTIONS = {
    "{kicad_sch}": "*.kicad_sch",
    "{kicad_pcb}": "*.kicad_pcb",
}


def find_files(workspace: pathlib.Path, pattern: str) -> list[pathlib.Path]:
    """Glob with a preference for the canonical spec-named file.

    If the glob matches multiple files (e.g. debug _*.kicad_sch files scattered
    by an iterating agent), prefer the one whose name matches the project base
    name implied by `eval_spec['id']` or the run manifest. Otherwise pick
    alphabetically first.
    """
    matches = sorted(workspace.glob(pattern))
    if not matches:
        return matches
    # Prefer the canonical file (no underscore prefix, no 'nolib' suffix)
    canonical = [m for m in matches if not m.name.startswith('_') and 'nolib' not in m.name.lower()]
    if canonical:
        return canonical
    return matches


def run_deterministic(check: dict, workspace: pathlib.Path) -> dict:
    """Run one deterministic check and return a dict with pass/fail + evidence."""
    name = check["name"]
    if "command" in check:
        cmd = check["command"]
        for k, v in SUBSTITUTIONS.items():
            cmd = cmd.replace(k, v)
        # Resolve glob for files matching *.kicad_sch / *.kicad_pcb
        for k, v in SUBSTITUTIONS.items():
            if v in cmd:
                files = find_files(workspace, v)
                if not files:
                    return {"name": name, "pass": False, "reason": f"no files match {v}"}
                cmd = cmd.replace(v, str(files[0]))
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=60,
                cwd=str(workspace),
            )
            passed = (proc.returncode == 0) if "exit_code" in check.get("pass", "exit_code == 0") else True
            return {
                "name": name,
                "pass": passed,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:5000],
                "stderr": proc.stderr[:5000],
            }
        except subprocess.TimeoutExpired:
            return {"name": name, "pass": False, "reason": "command timeout"}
    elif "check" in check:
        expr = check["check"]
        for k, v in SUBSTITUTIONS.items():
            expr = expr.replace(k, v)
        for k, v in SUBSTITUTIONS.items():
            if v in expr:
                files = find_files(workspace, v)
                if not files:
                    return {"name": name, "pass": False, "reason": f"no files match {v}"}
                expr = expr.replace(v, str(files[0]))
        try:
            proc = subprocess.run(expr, shell=True, capture_output=True, text=True, timeout=30,
                                   cwd=str(workspace))
            return {
                "name": name,
                "pass": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": proc.stdout[:2000],
                "stderr": proc.stderr[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"name": name, "pass": False, "reason": "check timeout"}
    return {"name": name, "pass": False, "reason": "no command or check in spec"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True, help="path to run output dir")
    ap.add_argument("--no-llm", action="store_true", help="skip LLM judge")
    ap.add_argument("--cross-grade", action="store_true",
                    help="invoke a separate CLI cross-grader")
    ap.add_argument("--cross-agent", default="codex")
    ap.add_argument("--cross-model", default="gpt-5.6-luna")
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    if not (run_dir / "run.json").exists():
        sys.exit(f"run.json not found in {run_dir}")
    run = json.loads((run_dir / "run.json").read_text())

    # Find the spec the run came from
    spec_path = find_spec_for_run(run)
    if not spec_path:
        sys.exit(f"could not find spec for eval {run['spec_id']}")
    import yaml
    spec = yaml.safe_load(spec_path.read_text())

    workspace = pathlib.Path(run["workspace"]).resolve()
    if not workspace.exists():
        sys.exit(f"workspace not found: {workspace}")

    # Run deterministic checks
    det_results = []
    for chk in spec["grading"]["deterministic"]:
        det_results.append(run_deterministic(chk, workspace))

    det_score = sum(1 for r in det_results if r["pass"]) / max(1, len(det_results))

    # LLM judge (if enabled)
    llm_result = None
    if spec["grading"]["llm_judge"]["enabled"] and not args.no_llm:
        # Skip if no artifacts to grade
        if not list(workspace.glob("*.kicad_*")):
            llm_result = {"pass": False, "reason": "no kicad artifacts to grade"}
        else:
            # The actual LLM judge is invoked via cross_grade.py. Here we just
            # record the plan.
            llm_result = {"pass": "DEFERRED", "model": spec["grading"]["llm_judge"]["model"]}

    weights = spec["grading"]["weights"]
    if llm_result and isinstance(llm_result.get("pass"), bool):
        score = (
            weights["deterministic"] * det_score
            + weights["llm_judge"] * (1.0 if llm_result["pass"] else 0.0)
        )
    else:
        score = det_score

    passed = score >= spec["passing_threshold"]
    grade = {
        "run_id": run["run_id"],
        "spec_id": run["spec_id"],
        "agent": run["agent"],
        "model": run["model"],
        "deterministic": det_results,
        "deterministic_score": det_score,
        "llm_judge": llm_result,
        "final_score": score,
        "passing_threshold": spec["passing_threshold"],
        "passed": passed,
        "graded_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    (run_dir / "grade.json").write_text(json.dumps(grade, indent=2))
    print(f"[grader] deterministic {det_score:.2f} ({sum(1 for r in det_results if r['pass'])}/{len(det_results)})")
    print(f"[grader] final {score:.2f} (threshold {spec['passing_threshold']})")
    print(f"[grader] VERDICT: {'PASS' if passed else 'FAIL'}")


def find_spec_for_run(run: dict) -> pathlib.Path | None:
    """Walk the evals/ directory and find the spec with matching id."""
    import yaml
    here = pathlib.Path(__file__).resolve().parent
    project_root = here.parent
    for f in sorted(project_root.glob("evals/*.yaml")):
        try:
            data = yaml.safe_load(f.read_text())
            if data.get("id") == run["spec_id"]:
                return f
        except Exception:
            continue
    return None


if __name__ == "__main__":
    main()
