# Agent Evals — top-level Makefile
#
# Concurrency-safe wrappers around the harness. Use make targets rather than
# calling runner.py directly so we get consistent flags, log paths, and cost.

# Lockfile to prevent concurrent runs from corrupting results.json
LOCK := /tmp/agent-evals.lock

# Allocating CLIs:
# - claude-code:  bounded by --max-budget-usd
# - codex:        for cross-grading only (no impl runs)
# - cursor-agent: cross-grading only (composer-2.5)
# - coder-codex:  reserved for codex-built implementer profile

KICAD_IMAGE ?= kicad/kicad:9.0
LLM_JUDGE_MODEL ?= gpt-5.6-luna
GRADER_MODEL ?= gpt-5.6-luna

.PHONY: list run-001 run-002 run-003 run-004 run-005 run-006 \
        grade cross-grade aggregate serve install clean status verify

# Show all eval specs
list:
	@ls -1 evals/*.yaml

# Convenience targets for each eval run
run-001: ; $(MAKE) run-eval EVAL=led-blinky-minimal
run-002: ; $(MAKE) run-eval EVAL=led-blinky-minimal AGENT=cursor-agent MODEL=composer-2.5
run-003: ; $(MAKE) run-eval EVAL=bme280-sensor-breakout
run-004: ; $(MAKE) run-eval EVAL=usb-c-host-only
run-005: ; $(MAKE) run-eval EVAL=esp32-devboard-minimal
run-006: ; $(MAKE) run-eval EVAL=two-layer-impedance-match

# Canonical run-eval
EVAL ?= led-blinky-minimal
AGENT ?= claude-code
MODEL ?= claude-sonnet-4-6
MAX_BUDGET ?= 2.0
MAX_TURNS ?= 60
RUN_NAME ?= run-$(EVAL)-$(AGENT)
run-eval:
	@mkdir -p results/runs/$(RUN_NAME)/workspace
	flock $(LOCK) -c 'python3 harness/runner.py --spec evals/$(EVAL).yaml --agent $(AGENT) --model $(MODEL) --max-budget $(MAX_BUDGET) --max-turns $(MAX_TURNS) --interactive --workspace-dir results/runs/$(RUN_NAME)/workspace --output-dir results/runs/$(RUN_NAME) 2>&1 | tee results/runs/$(RUN_NAME)/live.log'
	@python3 harness/grader.py --run results/runs/$(RUN_NAME) 2>&1 | tee -a results/runs/$(RUN_NAME)/live.log
	@python3 harness/aggregate.py

# Per-run grading (no re-run)
RUN_DIR ?= results/runs/run-001-led-blinky
grade:
	@python3 harness/grader.py --run $(RUN_DIR)

# Cross-CLI validation
RUN_DIR ?= results/runs/run-001-led-blinky
CROSS_AGENT ?= codex
CROSS_MODEL ?= gpt-5.6-luna
CROSS_PROMPT ?= "Inspect the kicad files in this workspace. Verify ERC and DRC pass and gerbers are present. Summarize in 3 lines."
cross-grade:
	@python3 harness/cross_grade.py --run $(RUN_DIR) --agent $(CROSS_AGENT) --model $(CROSS_MODEL) --prompt $(CROSS_PROMPT)

# Rebuild results.json
aggregate:
	@python3 harness/aggregate.py

# Serve the static site locally
serve:
	@python3 -m http.server 8000 --directory site

# Verify the harness itself (parse evals, check Python files)
verify:
	@python3 -c "import yaml, glob; [yaml.safe_load(open(f)) for f in glob.glob('evals/*.yaml')]; print('All eval YAMLs parse OK')"
	@python3 -c "import ast, pathlib; [ast.parse(pathlib.Path(f).read_text()) for f in pathlib.Path('harness').glob('*.py')]; print('All harness Python files parse OK')"
	@ls -la evals/ harness/ site/

# Install KiCad eval environment (Docker)
install:
	docker pull $(KICAD_IMAGE)
	docker build -t agent-evals:0.1 harness/

# Show quota state
status:
	@bash /home/ragiton/.hermes/snapshots/ration-allocator.sh

# Clean (does NOT remove results.json — only stale runs)
clean:
	find results/runs -mindepth 1 -maxdepth 1 -type d -mtime +14 -exec rm -rf {} +
