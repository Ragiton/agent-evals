# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Ragiton
#!/usr/bin/env python3
"""
Agent Evals — cross_grade.py

Invokes a DIFFERENT CLI than the one that ran the eval, gets its verdict on
the captured artifacts, and records it. This is the cross-CLI validation
step. Never Hermes — always one of the CLIs.

Usage:
  python harness/cross_grade.py --run results/runs/<run-id>/ \\
      --agent codex --model gpt-5.6-luna \\
      --prompt "Inspect the kicad files in this workspace, list component refs, verify the 555 wiring..."
"""
from __future__ import annotations
import argparse, json, pathlib, subprocess, sys, datetime

AGENTS = {
    "claude-code": ["claude", "-p", "--permission-mode", "bypassPermissions",
                    "--model", "{model}", "--max-turns", "5"],
    "codex": ["codex", "exec", "--no-alt-screen", "-C", "{workspace}",
              "--model", "{model}", "--dangerously-bypass-approvals-and-sandbox"],
    "cursor-agent": ["cursor-agent", "-p", "--trust", "--model", "{model}",
                     "--output-format", "json"],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--agent", required=True, choices=list(AGENTS.keys()))
    ap.add_argument("--model", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--max-budget", type=float, default=0.5)
    args = ap.parse_args()

    run_dir = pathlib.Path(args.run).resolve()
    if not (run_dir / "run.json").exists():
        sys.exit(f"run.json not found in {run_dir}")
    run = json.loads((run_dir / "run.json").read_text())
    workspace = pathlib.Path(run["workspace"]).resolve()

    cmd = []
    for tok in AGENTS[args.agent]:
        if tok == "{model}":
            cmd.append(args.model)
        elif tok == "{workspace}":
            cmd.append(str(workspace))
        else:
            cmd.append(tok)
    if args.agent == "claude-code" and args.max_budget > 0:
        cmd += ["--max-budget-usd", str(args.max_budget)]

    print(f"[cross_grade] invoking {args.agent} ({args.model}) on {workspace}")
    try:
        proc = subprocess.run(cmd, input=args.prompt, capture_output=True,
                              text=True, timeout=60 * 10)
        out = proc.stdout
        err = proc.stderr
        rc = proc.returncode
    except subprocess.TimeoutExpired:
        out, err, rc = "", "TIMEOUT", 124

    cross = {
        "agent": args.agent,
        "model": args.model,
        "exit_code": rc,
        "prompt": args.prompt,
        "stdout": out[:20000],
        "stderr": err[:5000],
        "graded_at": datetime.datetime.utcnow().isoformat() + "Z",
    }
    (run_dir / f"cross_grade_{args.agent}.json").write_text(json.dumps(cross, indent=2))
    print(f"[cross_grade] exit_code={rc}; written to cross_grade_{args.agent}.json")
    print(out[:2000])


if __name__ == "__main__":
    main()
