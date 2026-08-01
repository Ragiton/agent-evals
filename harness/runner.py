# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
#!/usr/bin/env python3
"""
Agent Evals — runner.py

Takes a spec.yaml + agent config, launches the chosen CLI in a fresh workspace,
captures artifacts. Optionally invokes a separate cross-grader CLI.

Cost rules (HARD):
  - Never invokes Hermes as final verifier.
  - Final verifier is always one of: claude-code, codex, cursor-agent.
  - Caps run time via --max-runtime and (where supported) --max-budget-usd.
  - Records every dollar spent / token used into results.json.

Usage:
  python harness/runner.py --spec evals/01-led-blinky-minimal.yaml \\
                            --agent claude-code --model claude-sonnet-4-6 \\
                            --max-runtime 30m --max-budget 1.0 --max-turns 40

  python harness/runner.py --spec evals/01-led-blinky-minimal.yaml \\
                            --agent claude-code --model claude-sonnet-4-6 \\
                            --count 3 --max-budget 1.0 --max-turns 40

NOTES for the implementation subagent:
  - Spec resolution: read --spec, substitute {kicad_sch}, {kicad_pcb} in checks.
  - Workspace: use --workspace-dir or default to ./results/runs/<run-id>/
  - Artifacts: copy/move from workspace/<expected-outputs> back to results/runs/<run-id>/artifacts/
  - results.json: one entry per run with all artifact paths and grading results.
  - The runner does NOT call Hermes. It launches a CLI subprocess and waits.
"""
from __future__ import annotations
import argparse, json, os, secrets, subprocess, sys, time, pathlib, shlex, datetime, shutil

AGENTS = {
    "claude-code": {
        "cmd": ["claude", "-p", "--permission-mode", "bypassPermissions",
                "--model", "{model}", "--max-turns", "{max_turns}"],
        "cost_flag": "--max-budget-usd",
        "model_default": "claude-sonnet-4-6",
        "stdin_mode": True,
    },
    "codex": {
        "cmd": ["codex", "exec", "--no-alt-screen",
                "-C", "{workspace}",
                "--model", "{model}",
                "--dangerously-bypass-approvals-and-sandbox"],
        "cost_flag": None,
        "model_default": "gpt-5.6-luna",
        "stdin_mode": True,
    },
    "cursor-agent": {
        "cmd": ["cursor-agent", "-p", "--trust", "--output-format", "json",
                "--model", "{model}"],
        "cost_flag": None,
        "model_default": "composer-2.5",
        "stdin_mode": True,
    },
    "coder-codex": {
        "cmd": ["claude", "-p", "--permission-mode", "bypassPermissions",
                "--model", "{model}",
                "--append-system-prompt", "You are running inside the agent-evals harness. "
                "Use the openai-codex provider via Hermes when given a token; do not infer it."],
        "cost_flag": "--max-budget-usd",
        "model_default": "gpt-5.6-luna",
        "stdin_mode": True,
    },
}


def make_run_id() -> str:
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


def _build_cmd(agent_cfg: dict, model: str, max_turns: int, workspace: pathlib.Path, max_budget: float) -> list[str]:
    cmd = []
    for tok in agent_cfg["cmd"]:
        if tok == "{model}":
            cmd.append(model)
        elif tok == "{workspace}":
            cmd.append(str(workspace))
        elif tok == "{max_turns}":
            cmd.append(str(max_turns))
        else:
            cmd.append(tok)
    if agent_cfg["cost_flag"] and max_budget > 0:
        cmd += [agent_cfg["cost_flag"], str(max_budget)]
    return cmd


def _execute_run(
    cmd: list[str],
    prompt: str,
    output_dir: pathlib.Path,
    workspace: pathlib.Path,
    run_id: str,
    spec_id: str,
    agent: str,
    model: str,
    max_budget: float,
    max_turns: int,
    max_runtime: str,
    condition: str | None,
    interactive: bool,
) -> int:
    """Execute one agent invocation, write run.json, return exit_code."""
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace.mkdir(parents=True, exist_ok=True)

    manifest: dict = {
        "run_id": run_id,
        "spec_id": spec_id,
        "agent": agent,
        "model": model,
        "condition": condition,
        "max_budget_usd": max_budget,
        "max_turns": max_turns,
        "max_runtime": max_runtime,
        "workspace": str(workspace),
        "output_dir": str(output_dir),
        "started_at": datetime.datetime.utcnow().isoformat() + "Z",
        "argv": cmd,
        "prompt_chars": len(prompt),
    }
    (output_dir / "run.json").write_text(json.dumps(manifest, indent=2))
    print(f"[runner] starting {agent} ({model}) for {spec_id}")
    print(f"[runner] run_id = {run_id}")

    if interactive:
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60 * 30,
            )
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode
        except subprocess.TimeoutExpired:
            stdout, stderr, exit_code = "", "TIMEOUT after 30m", 124
    else:
        stdout, stderr, exit_code = "INTERACTIVE MODE OFF", "", 0

    (output_dir / "stdout.txt").write_text(stdout or "")
    (output_dir / "stderr.txt").write_text(stderr or "")

    manifest.update({
        "exit_code": exit_code,
        "finished_at": datetime.datetime.utcnow().isoformat() + "Z",
        "stdout_chars": len(stdout or ""),
    })
    (output_dir / "run.json").write_text(json.dumps(manifest, indent=2))
    print(f"[runner] exit_code={exit_code}")
    print(f"[runner] results in: {output_dir}")
    return exit_code


def _is_successful_run(run_dir: pathlib.Path) -> bool:
    """Return True if the slot has a successful run (exit_code==0 AND graded AND passed==true)."""
    run_json = run_dir / "run.json"
    if not run_json.exists():
        return False
    try:
        run = json.loads(run_json.read_text())
        if run.get("exit_code") != 0:
            return False
    except Exception:
        return False
    # Check grade data in new or old location
    grade_json = run_dir / "grade.json"
    grades_det = run_dir / "grades" / "deterministic" / "grade.json"
    grade_data = None
    if grade_json.exists():
        try:
            g = json.loads(grade_json.read_text())
            if "graders" in g and "paths" in g:
                det = run_dir / g["paths"].get("deterministic", "grades/deterministic/grade.json")
                if det.exists():
                    grade_data = json.loads(det.read_text())
            else:
                grade_data = g
        except Exception:
            pass
    elif grades_det.exists():
        try:
            grade_data = json.loads(grades_det.read_text())
        except Exception:
            pass
    return grade_data is not None and grade_data.get("passed") is True


def _archive_run(run_dir: pathlib.Path) -> None:
    """Move a failed run slot to an archive directory so the slot can be reused."""
    timestamp = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    archive = run_dir.parent / f"{run_dir.name}.failed-{timestamp}"
    shutil.move(str(run_dir), str(archive))
    print(f"[runner] archived failed run to {archive.name}")


def _call_grader(run_dir: pathlib.Path) -> bool:
    """Invoke grader.py on a completed run dir. Return True if grader succeeded."""
    grader = pathlib.Path(__file__).resolve().parent / "grader.py"
    try:
        result = subprocess.run(
            [sys.executable, str(grader), "--run", str(run_dir)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            print(f"[runner] grader exited {result.returncode}: {result.stderr[:200]}")
            return False
        return True
    except Exception as exc:
        print(f"[runner] grader call failed: {exc}")
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--agent", required=True, choices=list(AGENTS.keys()))
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-runtime", default="30m")
    ap.add_argument("--max-budget", type=float, default=2.0,
                    help="USD cap (applied to claude-code only via --max-budget-usd)")
    ap.add_argument("--max-turns", type=int, default=60,
                    help="Maximum turns for the agent (applied to claude-code via --max-turns)")
    ap.add_argument("--count", type=int, default=1,
                    help="Target number of successful completed runs (smevals-style top-up)")
    ap.add_argument("--condition", default=None,
                    help="Label this run with a condition tag (e.g. 'baseline')")
    ap.add_argument("--workspace-dir", default=None)
    ap.add_argument("--output-dir", default=None)
    ap.add_argument("--dry-run", action="store_true",
                    help="Print the resolved command and exit")
    ap.add_argument("--interactive", action="store_true",
                    help="If set, run the CLI inline (used by harness self-test)")
    args = ap.parse_args()

    spec_path = pathlib.Path(args.spec).resolve()
    if not spec_path.exists():
        sys.exit(f"spec not found: {spec_path}")

    import yaml
    spec = yaml.safe_load(spec_path.read_text())

    agent_cfg = AGENTS[args.agent]
    model = args.model or agent_cfg["model_default"]

    # --count 1 (default): original single-shot behavior, random run ID
    if args.count <= 1:
        run_id = make_run_id()
        workspace = pathlib.Path(args.workspace_dir or f"results/runs/{run_id}/workspace").resolve()
        output_dir = pathlib.Path(args.output_dir or f"results/runs/{run_id}").resolve()
        cmd = _build_cmd(agent_cfg, model, args.max_turns, workspace, args.max_budget)

        if args.dry_run:
            print("DRY RUN")
            print(f"  spec:      {spec_path}")
            print(f"  agent:     {args.agent}")
            print(f"  model:     {model}")
            print(f"  max-turns: {args.max_turns}")
            print(f"  workspace: {workspace}")
            print(f"  output:    {output_dir}")
            print(f"  cmd:       {shlex.join(cmd)}")
            print(f"  prompt:    {spec['prompt'][:200]}...")
            return

        _execute_run(
            cmd, spec["prompt"], output_dir, workspace,
            run_id, spec["id"], args.agent, model,
            args.max_budget, args.max_turns, args.max_runtime, args.condition,
            args.interactive,
        )
        return

    # --count N > 1: resumable top-up with deterministic run IDs
    spec_id = spec.get("id", pathlib.Path(args.spec).stem)
    runs_dir = (pathlib.Path(__file__).resolve().parent.parent / "results" / "runs")
    runs_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        dummy_ws = runs_dir / f"{spec_id}-{args.agent}-01" / "workspace"
        cmd = _build_cmd(agent_cfg, model, args.max_turns, dummy_ws, args.max_budget)
        print(f"DRY RUN (--count {args.count})")
        print(f"  spec:      {spec_path}")
        print(f"  agent:     {args.agent}")
        print(f"  model:     {model}")
        print(f"  max-turns: {args.max_turns}")
        print(f"  run-ids:   {spec_id}-{args.agent}-01 .. {spec_id}-{args.agent}-{args.count*3:02d}")
        print(f"  cmd:       {shlex.join(cmd)}")
        return

    successful = 0
    attempts = 0
    max_attempts = args.count * 3
    slot = 0

    while successful < args.count and attempts < max_attempts:
        slot += 1
        run_id = f"{spec_id}-{args.agent}-{slot:02d}"
        slot_dir = runs_dir / run_id
        workspace = slot_dir / "workspace"

        if slot_dir.exists():
            if _is_successful_run(slot_dir):
                successful += 1
                print(f"[runner] slot {run_id}: already successful, skipping ({successful}/{args.count})")
                continue
            else:
                _archive_run(slot_dir)

        cmd = _build_cmd(agent_cfg, model, args.max_turns, workspace, args.max_budget)
        exit_code = _execute_run(
            cmd, spec["prompt"], slot_dir, workspace,
            run_id, spec_id, args.agent, model,
            args.max_budget, args.max_turns, args.max_runtime, args.condition,
            args.interactive,
        )
        attempts += 1

        if exit_code == 0:
            _call_grader(slot_dir)
            if _is_successful_run(slot_dir):
                successful += 1
                print(f"[runner] slot {run_id}: successful ({successful}/{args.count})")
            else:
                print(f"[runner] slot {run_id}: agent exited 0 but grader found failure")
        else:
            print(f"[runner] slot {run_id}: exit_code={exit_code}, not counting as success")

    if successful < args.count:
        print(f"[runner] WARNING: only {successful}/{args.count} successful runs after {attempts} attempts (max_attempts={max_attempts})")
    else:
        print(f"[runner] done: {successful}/{args.count} successful runs")


if __name__ == "__main__":
    main()
