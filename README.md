# Agent Evals

[![License: GPL v3+](https://img.shields.io/badge/License-GPLv3+-blue.svg)](LICENSE)
[![Website](https://img.shields.io/badge/website-ragiton.github.io%2Fagent--evals-blue)](https://ragiton.github.io/agent-evals/)

Personal eval harness for engineering AI agents. Specification is the contract; run is the experiment; `results.json` is the truth.

Released under **GPL-3.0-or-later**. Any derivative work that you distribute must remain under the same license, with source available — see [`LICENSE`](LICENSE).

## Layout

```
agent-evals/
├── evals/                    # 6 KiCad eval specs (YAML)
│   ├── 01-led-blinky-minimal.yaml
│   ├── 02-bme280-sensor-breakout.yaml
│   ├── 03-buck-converter-3v3.yaml
│   ├── 04-usb-c-host-only.yaml
│   ├── 05-esp32-devboard-minimal.yaml
│   └── 06-two-layer-impedance-match.yaml
├── skills/                   # Two pinned skill/MCPs we're evaluating
│   ├── mash-kicad-skills/    # file/CLI baseline
│   └── konnect/              # live MCP
├── harness/                  # runner.py + grader.py + cross_grade.py + aggregate.py + Dockerfile
├── site/                     # Static HTML results site (reads results.json)
├── results/                  # results.json + runs/<run-id>/{run.json,grade.json,artifacts/}
├── research/                 # Research outputs (kicad-skills-mcps.md)
├── CLAUDE.md                 # Project rules for the agent
├── Makefile                  # Top-level workflow
└── README.md
```

## Locked model assignments

| Role | CLI | Model | Provider |
|---|---|---|---|
| Implementation (this slice) | `claude-code` | `claude-sonnet-4-6` | Anthropic |
| Verification | `codex` | `gpt-5.6-luna` | OpenAI Codex OAuth |
| Cross-CLI validation | `cursor-agent` | `composer-2.5` | Cursor |
| Hermes intake/watcher | `MiniMax-M3` | `minimax-oauth` | MiniMax |

## Hard rules

- **Hermes never verifies.** Final verdict is always one of the CLIs above.
- **Forbidden paths**: `/home/ragiton/projects/.openacp`, `/home/ragiton/.codex/auth.json`, `/home/ragiton/.cursor/auth.json`, browser cookie DBs, OAuth/keyring files, raw provider payloads.
- **Secret redaction ON** — never paste API keys, tokens, or cookies into eval logs or results.json.
- **Cost cap**: do not exceed 50% of any CLI subscription's remaining weekly (or Cursor's weekly equivalent of monthly) quota.
- **Spec is unambiguous**: each `evals/*.yaml` must be runnable by an unattended agent without human interpretation.

## Workflow

```bash
# 1. Verify harness
make verify

# 2. Run an eval
make run-001   # claude-code on led-blinky-minimal
make run-002   # cursor-agent on led-blinky-minimal

# 3. Grade it (deterministic + LLM judge)
make grade RUN_DIR=results/runs/run-001-led-blinky

# 4. Cross-grade with a different CLI
make cross-grade RUN_DIR=results/runs/run-001-led-blinky

# 5. Rebuild results.json
make aggregate

# 6. View the leaderboard
make serve
# open http://localhost:8000
```

## Cost tracking

Live quota state: `make status` → `ration-allocator.sh`.

Spending rules per the existing subscription rationing policy:
- Use full quotas — pull bounded backlog slices forward.
- Stop when an individual run is too expensive to validate, not after the budget is gone.
- Cross-CLI verification is preferred when possible.

## Six KiCad evals (current iteration)

1. **led-blinky-minimal** — USB-C-powered 555 timer, 1 Hz blink
2. **bme280-sensor-breakout** — I2C sensor breakout, 4-pin header
3. **buck-converter-3v3** — TPS54331DR step-down, 12V→3.3V at 3A
4. **usb-c-host-only** — USB-C receptacle with CC pulldowns + ESD
5. **esp32-devboard-minimal** — ESP32-WROOM-32E + USB-UART + boot/reset
6. **two-layer-impedance-match** — 4-layer board with 90Ω USB diff pair

All graded on: ERC + DRC pass, gerbers export, BOM present, semantic LLM judge via gpt-5.6-luna.

## Two skill/MCP arms

- **mash/kicad-skills** (file/CLI baseline, controlled mutations)
- **mixelpixx/Konnect** (live KiCad 10 IPC MCP, 185 tools)

Both will be evaluated against all 6 evals (12 total runs minimum). Verdict matrix in results.json.

## How to add a new eval

1. Copy `evals/01-led-blinky-minimal.yaml` to `evals/07-my-new-eval.yaml`
2. Edit the spec (id, title, description, requirements, grading).
3. Make sure `grading.deterministic` includes entries that the canary CLI can run.
4. `make verify` to confirm it parses.
5. Run: `make run-eval EVAL=07-my-new-eval`.

## How to add a new skill/MCP

1. Add a folder under `skills/<name>/` with a README.md pinning the repo, license, install steps, and last-update date.
2. Add a `results-runs/<run-id>/cross_grade_<skill>.json` after a real run.
3. Update `skills/<name>/README.md` with the eval scoring dimensions.

## Snapshot policy

After every successful run, copy the entire `agent-evals/` tree to `~/.hermes/snapshots/agent-evals-<timestamp>/`. This is the rollback target if the harness itself gets corrupted.
