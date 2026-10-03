# Agent Evals

[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3+-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/Website-ragiton.github.io%2Fagent--evals-blue)](https://ragiton.github.io/agent-evals/)

Personal evaluation harness for engineering agents. A specification defines the task; a run is the experiment; results.json is the evidence.

Released under GPL-3.0-or-later. Distributed derivatives must remain under the same license; see LICENSE.

## Current operating model

Codex is the user's primary assistant and the default harness agent. New Codex runs use the native Codex CLI with GPT-6 Luna. Claude Code and Cursor adapters remain available only as explicitly selected benchmark subjects; they are not part of the user's normal assistant workflow.

Hermes, its provider routing, watchers, and snapshot paths are retired. Do not route Codex through Hermes or use old Hermes instructions. Historical Hermes runs remain in saved results as experiment evidence.

The OpenAI Codex changelog checked 2026-10-03 lists GPT-6 Luna in Codex and notes lower token prices than GPT-5.6 predecessors: https://learn.chatgpt.com/docs/changelog.

## Layout

- evals/ — six KiCad task specifications.
- skills/ — pinned snapshots of the skill and MCP arms under evaluation.
- harness/ — runner, deterministic grader, cross-grader, aggregator, cost helpers, and Docker image.
- site/ — static results page.
- results/ and docs/results.json — saved experiment outputs; preserve them.
- research/ — background research on KiCad skills and MCPs.
- AGENTS.md — current Codex instructions.
- CLAUDE.md — applies only when Claude Code is deliberately selected as an experiment subject.
- HANDOFF.md — archived July 2026 session note.
- Makefile — common evaluation commands.

## Evaluation scope

The six KiCad tasks are:

1. led-blinky-minimal — USB-C powered 555 timer, 1 Hz blink.
2. bme280-sensor-breakout — I2C sensor breakout with a four-pin header.
3. buck-converter-3v3 — TPS54331DR step-down, 12V to 3.3V at 3A.
4. usb-c-host-only — USB-C receptacle with CC pulldowns and ESD.
5. esp32-devboard-minimal — ESP32-WROOM-32E with USB-UART and boot/reset.
6. two-layer-impedance-match — 4-layer board with a 90-ohm USB differential pair.

The two tool arms compare mash/kicad-skills (file/CLI baseline with controlled mutations) and mixelpixx/Konnect (live KiCad IPC MCP). Existing specifications and results preserve earlier locked model assignments for reproducibility. Do not interpret those values as current model availability, pricing, quota, or user workflow.

## Run and inspect

- Run make verify to check the YAML specs and Python syntax.
- Run make run-001 for the default Codex evaluation.
- Run make run-002 only when a Cursor comparison is intended.
- Use make grade to grade a saved run, make cross-grade for a selected verifier, make aggregate to rebuild results, and make serve to preview the static site.
- Use make status to inspect the local Git working tree. It does not report provider quotas.
- The results/eval_matrix.json cells have no current approval; recheck the environment and explicitly approve an experiment before using the dispatcher.

The runner creates a per-run workspace. Codex runs use workspace-write sandboxing and do not bypass the sandbox. Keep credentials, tokens, cookies, auth files, and raw provider payloads out of prompts, logs, and results. Review exact paths and the staged diff before committing.

## Add an evaluation

1. Copy an existing YAML spec to a new file under evals/.
2. Edit its ID, title, description, requirements, and grading.
3. Make deterministic checks observable and reproducible.
4. Review the spec and environment before enabling a matrix cell.
5. Record the chosen agent, model, tool arm, artifacts, and grading evidence with the run.

## Add a skill or MCP arm

1. Add a folder under skills/ with a README that pins the source repository, license, install steps, and review date.
2. Add a real run and cross-grade result before describing its score.
3. Update the arm's README with the evaluation dimensions.

## Preserve experiment data

Keep specifications, research, and recorded run results. Existing Claude, Cursor, and Hermes result records are historical evidence, not operating instructions. Use Git history for rollback; do not copy the repository into retired Hermes snapshot directories.
