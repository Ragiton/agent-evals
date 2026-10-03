# Agent Evals

This document applies only when Claude Code is deliberately selected as a benchmark subject. Codex remains the user's primary assistant and owns normal project work.

## Evaluation scope

This iteration contains six KiCad eval specs: led-blinky-minimal, bme280-sensor-breakout, buck-converter-3v3, usb-c-host-only, esp32-devboard-minimal, and two-layer-impedance-match.

The benchmark compares pinned skill and MCP arms. The specification is the contract; the run is the experiment; results are the evidence.

## Operating boundaries

- Run only the explicitly selected evaluation and tool arm.
- Use the harness's isolated run workspace and keep artifacts under the run directory.
- Never route Codex through Hermes. Hermes and its provider router have been retired.
- Keep credentials, tokens, cookies, auth files, and raw provider payloads out of eval logs and results.
- Historical model assignments and quota snapshots in prior results are records, not current model or billing guidance.
- Preserve existing specs, research, and results unless the user explicitly requests changing them.

## Workflow

Read AGENTS.md and README.md for current Codex-centered project guidance. Use the Makefile for the selected run, grading, aggregation, and site preview. Record the exact agent, model, condition, artifacts, and grading evidence for any new experiment.

The old cross-CLI roles, Hermes intake, watcher, quota allocator, and local snapshot paths are not active operating instructions.
