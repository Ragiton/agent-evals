# Agent Evals — Session Handoff

**Date:** 2026-07-25 22:16 MDT
**Status:** Phase 1 (scaffold + first eval run) complete. Eval runs in progress.

## What's done

### Project
- `/home/ragiton/projects/agent-evals/` — fully scaffolded
- CLAUDE.md, README.md, Makefile, .gitignore — committed to git (commit 708f711)
- Snapshot at `~/.hermes/snapshots/agent-evals-2026-07-25/`

### 6 KiCad eval specs
- `evals/01-led-blinky-minimal.yaml` — USB-C 555 timer, difficulty 1
- `evals/02-bme280-sensor-breakout.yaml` — I2C sensor, difficulty 2
- `evals/03-buck-converter-3v3.yaml` — TPS54331DR, difficulty 4
- `evals/04-usb-c-host-only.yaml` — USB-C + ESD, difficulty 2
- `evals/05-esp32-devboard-minimal.yaml` — ESP32 + USB-UART, difficulty 3
- `evals/06-two-layer-impedance-match.yaml` — 4-layer diff pair, difficulty 5
- All parse with `yaml.safe_load`, all have deterministic grading + LLM judge

### Two skills/MCPs picked (research verified, not invented)
- **mash/kicad-skills** — file/CLI baseline, controlled mutations
- **mixelpixx/Konnect** — live KiCad 10 IPC MCP, 185 tools
- Full report: `research/kicad-skills-mcps.md` (verified reachability, installs, licenses)

### Harness
- `harness/runner.py` — launches claude-code/codex/cursor-agent, captures stdout/stderr
- `harness/grader.py` — deterministic checks via kicad-cli, deferred LLM judge
- `harness/cross_grade.py` — separate CLI for cross-CLI validation
- `harness/aggregate.py` — rebuilds results.json from run dirs
- `harness/Dockerfile` — kicad/kicad:9.0 base + ngspice + python tools

### Site
- `site/index.html` — single self-contained HTML, dark theme, monitor/operate surface
- Three views: Overview leaderboard, Per-eval detail, Per-run detail
- Reads `results/results.json` (no backend)
- Slop audit: 2/10 (no gradient, no icons, no glassmorphism, no hero, system mono not Inter as default)

### Kanban board
- New board `agent-evals` at `/home/ragiton/.hermes/kanban/boards/agent-evals/kanban.db`
- 5 cards: scaffold site, eval specs, harness, run-001, research
- All have loom comments with concrete progress

## What's running

- **run-002-led-blinky-cursor** (background, PID 1159813): claude-code sonnet-4-6 on led-blinky-minimal
  - Working dir: `results/runs/run-002-led-blinky-cursor/workspace/`
  - Budget cap: $2.00, max 80 turns
  - Started ~22:13 UTC, currently ~3 min in
  - No output yet (Claude streams at end)

## What's blocked

- **No kicad-cli on this machine.** Docker also not installed. The agent needs to either `apt install kicad` or hand-craft .kicad_sch files. Eval #1 will tell us which the agent picks.
- **Codex CLI binary not on PATH** (auth is wired in Hermes). Direct `codex` shell invocations from the runner don't work; only via Hermes `openai-codex` provider. The runner.py has a `coder-codex` agent that uses the openai-codex provider via Hermes.

## Cost spent so far (vs 50% budget cap)

- Claude Code: 3% used (97% remaining)
- Codex: 0% used (100% remaining)
- Cursor: 10% used (90% remaining)
- MiniMax: ~27% used (73% remaining)

All well within budget. The failed inline run-001 ate ~1% of Claude Code; the v2 background run-002 will eat ~2-3%.

## Next concrete steps (when run-002 finishes)

1. Grade run-002 with `python3 harness/grader.py --run results/runs/run-002-led-blinky-cursor`
2. Cross-grade with `python3 harness/cross_grade.py --run results/runs/run-002-led-blinky-cursor --agent codex --model gpt-5.6-luna --prompt "..."`
3. Decide whether to attempt run-001 redux with HARNESS=claude-code or skip to evals #2-6
4. Attempt a Cursor cross-grade run on the same eval (run-003 via makefile)
5. If kicad-cli install works, run the full 6-eval matrix
6. Snapshot state, commit, post handoff to JP

## Run instructions for JP

```bash
# See live status
make status
make list

# Once run-002 finishes, view results
python3 harness/aggregate.py
make serve
# open http://localhost:8000

# Rerun the first eval (after run-002 finishes)
make run-001
```
