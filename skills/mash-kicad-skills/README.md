# mash/kicad-skills — eval arm

**Repo:** https://github.com/mash/kicad-skills
**Type:** Claude Code plugin/skills + `kicad-tool` CLI wrapper
**Install:** `pipx install git+https://github.com/mash/kicad-skills.git` (or `uv tool install ...`)
**License:** No LICENSE file detected — legal ambiguity (issue to track)
**Tool surface:** `sch render-region/inspect/erc/netlist/validate`; `pcb drc/validate/render-region/sync`; footprint/zone/via edits; mutations support `--dry-run`; structured JSON.
**Last update:** 2026-06-06

## Eval role
This is the **controlled-file/CLI baseline**. The agent uses mash/kicad-skills to mutate .kicad_sch / .kicad_pcb files via the CLI wrapper, run validation, and emit gerbers. Compared against Konnect (live IPC).

## How to use from the agent
```bash
uv tool install git+https://github.com/mash/kicad-skills.git
kicad-tool --help
kicad-tool sch erc my.kicad_sch
kicad-tool pcb drc my.kicad_pcb
kicad-tool pcb render-region my.kicad_pcb --output out.png
```

## Eval scoring dimensions
- File validity (does the .kicad_pcb still open in KiCad afterwards?)
- Preservation of unrelated S-expressions/UUIDs
- Validation accuracy (does it catch real DRC errors?)
- Agent tool efficiency
