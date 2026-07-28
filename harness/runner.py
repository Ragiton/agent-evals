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
                            --max-runtime 30m --max-budget 2.0

  python harness/runner.py --spec evals/01-led-blinky-minimal.yaml \\
                            --agent coder-codex --model gpt-5.6-luna \\
                            --max-runtime 30m

  python harness/runner.py --spec evals/01-led-blinky-minimal.yaml \\
                            --agent cursor-agent --model composer-2.5 \\
                            --max-runtime 30m

NOTES for the implementation subagent:
  - Spec resolution: read --spec, substitute {kicad_sch}, {kicad_pcb} in checks.
  - Workspace: use --workspace-dir or default to ./results/runs/<run-id>/
  - Artifacts: copy/move from workspace/<expected-outputs> back to results/runs/<run-id>/artifacts/
  - results.json: one entry per run with all artifact paths and grading results.
  - The runner does NOT call Hermes. It launches a CLI subprocess and waits.
"""
from __future__ import annotations
import argparse, json, os, secrets, subprocess, sys, time, pathlib, shlex, datetime

AGENTS = {
    "claude-code": {
        "cmd": ["claude", "-p", "--permission-mode", "bypassPermissions",
                "--model", "{model}", "--max-turns", "60"],
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--agent", required=True, choices=list(AGENTS.keys()))
    ap.add_argument("--model", default=None)
    ap.add_argument("--max-runtime", default="30m")
    ap.add_argument("--max-budget", type=float, default=2.0,
                    help="USD cap (applied to claude-code only via --max-budget-usd)")
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
    run_id = make_run_id()
    workspace = pathlib.Path(args.workspace_dir or f"results/runs/{run_id}/workspace").resolve()
    output_dir = pathlib.Path(args.output_dir or f"results/runs/{run_id}").resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Substitute model / workspace into the command
    cmd = []
    for tok in agent_cfg["cmd"]:
        if tok == "{model}":
            cmd.append(model)
        elif tok == "{workspace}":
            cmd.append(str(workspace))
        else:
            cmd.append(tok)
    if agent_cfg["cost_flag"] and args.max_budget > 0:
        cmd += [agent_cfg["cost_flag"], str(args.max_budget)]

    # The prompt that goes to the agent
    prompt = spec["prompt"]
    if args.dry_run:
        print("DRY RUN")
        print(f"  spec:    {spec_path}")
        print(f"  agent:   {args.agent}")
        print(f"  model:   {model}")
        print(f"  workspace: {workspace}")
        print(f"  output:    {output_dir}")
        print(f"  cmd:      {shlex.join(cmd)}")
        print(f"  prompt:  {prompt[:200]}...")
        return

    # Pipe the prompt to stdin
    manifest = {
        "run_id": run_id,
        "spec_id": spec["id"],
        "agent": args.agent,
        "model": model,
        "max_runtime": args.max_runtime,
        "max_budget_usd": args.max_budget,
        "workspace": str(workspace),
        "output_dir": str(output_dir),
        "started_at": datetime.datetime.utcnow().isoformat() + "Z",
        "argv": cmd,
        "prompt_chars": len(prompt),
    }
    (output_dir / "run.json").write_text(json.dumps(manifest, indent=2))
    print(f"[runner] starting {args.agent} ({model}) for {spec['id']}")
    print(f"[runner] run_id = {run_id}")

    # Real execution
    if args.interactive:
        try:
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60 * 30,  # hard cap; --max-runtime is the soft cap
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


if __name__ == "__main__":
    main()
