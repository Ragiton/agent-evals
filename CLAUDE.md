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

## Harness upgrades (fea/smevals-upgrades-cost)

Four changes shipped together:

1. **Resumable `--count N` runner**: `runner.py` accepts `--count N`, `--max-turns`, `--condition`. Loops over slots `<spec-id>-<agent>-NN`; archives failed slots; calls grader after each; stops when one passes. Re-entrant: skips slots that already passed.
2. **Grader YAML snapshotting**: `grader.py` embeds `spec_snapshot` into every `results.json` / `grade.json`, capturing the deterministic checks list, llm_judge config, run manifest fields (agent, model, budget, turns, condition), spec version, and a timestamp. Enables audit without the original YAML.
3. **Co-located `grades/` layout**: `grader.py` writes the full grade result to `<run-dir>/grades/deterministic/grade.json`. The run-root `grade.json` becomes an **index manifest** (`schema_version`, `graders`, `paths`, `passed`, scores, `spec_snapshot`). `results.json` at the run root remains the legacy alias (full result). `aggregate.py` reads the manifest and follows the path pointer.
4. **`harness_error` status**: `aggregate.py` sets `status: "harness_error"` when exit_code != 0 or grade is missing. Site renders this as a distinct amber badge, tracked separately from `incomplete`.

### File layout after grading
```
results/<run-id>/
  run.json                          ← runner manifest
  grade.json                        ← index manifest (NEW)
  results.json                      ← legacy full result (backward compat)
  grades/
    deterministic/
      grade.json                    ← full grader output (NEW)
```

### Backward compatibility
- Existing runs without `grades/` still aggregate: `aggregate.py` falls back to the legacy full-result `grade.json`.
- `results.json` at the run root is always written (identical to `grades/deterministic/grade.json`).

## Cost discipline
- **Per-call cost** is captured from the CLI JSON envelope into `run.json` → `cost_usd` and `usage`. The site shows it per-run and in a top-of-page spend summary card.
- **Weekly budget cap**: never exceed 50% of any CLI subscription's remaining weekly quota (or Cursor's weekly-equivalent of monthly quota). Stop when the budget is hit.
- **Cost cap flag**: `--max-budget-usd N` passed to runner limits the per-run hard cap; `--max-turns N` limits turns. These are hints to the CLI, not guarantees.
- **Aggregator**: `python harness/aggregate.py` rebuilds `results/results.json` from all run dirs. Run after grading to refresh the site.
