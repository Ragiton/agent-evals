# Agent Evals

Personal eval harness for engineering AI agents. **Specification is the contract; run is the experiment; results.json is the truth.**

## Scope (this iteration: 6 KiCad evals)
1. led-blinky-minimal
2. bme280-sensor-breakout
3. buck-converter-3v3
4. usb-c-host-only
5. esp32-devboard-minimal
6. two-layer-impedance-match

## Locked model assignments
- **Claude Code (implementation)**: `claude-sonnet-4-6`
- **Codex (verification)**: `gpt-5.6-luna` via Hermes `openai-codex` provider
- **Cursor (cross-CLI validation)**: `composer-2.5`
- **Hermes (intake, watcher, summarizer)**: `MiniMax-M3` via `minimax-oauth`

## Hard rules
- **Hermes never verifies.** Final verdict is always one of the CLIs above.
- **Forbidden paths**: `/home/ragiton/projects/.openacp`, `/home/ragiton/.codex/auth.json`, `/home/ragiton/.cursor/auth.json`, browser cookie DBs, OAuth/keyring files, raw provider payloads.
- **Secret redaction on** — never paste API keys, tokens, or cookies into eval logs or results.json.
- **Cost cap**: do not exceed 50% of any CLI subscription's remaining weekly (or Cursor's weekly equivalent of monthly) quota. Stop when the budget is hit, not later.
- **Spec is unambiguous**: each `evals/*.yaml` must be runnable by an unattended agent without human interpretation.

## Layout
- `evals/` — YAML spec files (one per eval)
- `skills/` — pinned snapshots of skill/MCPs we're evaluating
- `harness/` — runner.py, grader.py, cli_helpers.py, Dockerfile
- `site/` — static HTML results site (single file, reads results.json)
- `results/` — run artifacts (gitignored), summary `results.json`
- `research/` — research outputs (e.g. kicad-skills-mcps.md)

## Run / grade loop
1. `python harness/runner.py --spec evals/led-blinky-minimal.yaml --agent claude-code --model claude-sonnet-4-6`
2. `python harness/grader.py --run results/<run-id>/`
3. `python harness/cross_grade.py --run results/<run-id>/ --agent codex --model gpt-5.6-luna`
4. Append to results.json (site re-reads on reload)
