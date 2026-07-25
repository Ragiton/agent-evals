# KiCad skills and MCP servers for coding agents

**Research date:** 2026-07-25  
**Method:** live GitHub API/search, repository clone and README/source inspection, GitHub release/license/CI metadata, PyPI/npm API checks, and clean Python-venv install smokes where practical. Repository “last update” means the latest commit (`pushedAt`/cloned HEAD), not GitHub’s noisier `updatedAt`. URLs below were reachable on the research date.

## Honest conclusion

The ecosystem is real but extremely young and noisy. GitHub search returns dozens of repos named `kicad-mcp`, many created in 2026 with zero stars, no release, no tests, and duplicated or aspirational claims. Registry presence is not validation. The official [`modelcontextprotocol/servers`](https://github.com/modelcontextprotocol/servers) tree contains **zero** KiCad entries. The specifically suggested `github.com/lifasdok/kicad-mcp` returns **404**.

### Ranked recommendation for this eval harness

1. **`mash/kicad-skills` — SOLID (best skill/CLI baseline).** Small, auditable, agent-native workflow with deterministic dry-run/query/edit/validate commands. Its clean venv install from GitHub and `kicad-tool --help` both succeeded here. It is less broad than the huge MCPs, which is a virtue for eval attribution.
2. **`mixelpixx/Konnect` — SOLID/BETA (best full MCP candidate).** Current successor to the most popular KiCad MCP; single Rust binary, official KiCad 10 IPC for live PCB edits, atomic schematic editing, `kicad-cli` checks/exports, 185 tools and bundled skills. Released v0.2.0 and actively tested, but beta and AGPL/commercial licensing must be accepted.
3. **`mixelpixx/KiCAD-MCP-Server` — SOLID but integration-heavy.** Mature, MIT, 1.6k stars, v2.4.0, 122 tools and 100+ test files; however Node + Python + KiCad SWIG/experimental IPC is materially harder and its own maintainer directs new development to Konnect.
4. **`aklofas/kicad-happy` — SOLID for review-only evals.** Excellent read-only analysis/DFM skill suite, easy agent installation and successful CI, but it does not create/layout boards. Use instead of Konnect only if the eval is design review rather than PCB construction.

**Final picked two:** `mash/kicad-skills` and `mixelpixx/Konnect`. They provide a useful contrast: controlled file/CLI skill versus broad live MCP, while both genuinely mutate KiCad designs and validate outputs.

## Rating rubric

- **SOLID:** reachable, concrete agent invocation, actual KiCad interaction, working examples/tests, current maintenance, and a usable license/install story.
- **RISKY:** real and callable, but experimental, stale, incomplete, misleading install, missing license, failing current CI, or overly narrow.
- **DEAD:** archived/404, or advertised install is no longer published. “DEAD” does not mean source cannot be revived.
- **Integration pain:** Low / Medium / High based on runtime count, KiCad coupling, client setup, and platform constraints.

## MCP candidates

### 1. Konnect

- **URL/repo:** https://github.com/mixelpixx/Konnect
- **Type:** MCP + native KiCad 10 plugin + six bundled agent skills
- **Real install (README):** download `konnect-pcm-v<version>-<platform>.zip`, then KiCad 10 → Plugin and Content Manager → **Install from File**; source alternative:
  ```bash
  cargo build --release -p konnect
  ```
  Configure the resulting binary as MCP `"command": "/path/to/konnect"`.
- **Tools exposed (README wording):** **“185 tools across 18 on-demand toolsets”** covering “Schematic capture, PCB layout and routing, ERC/DRC, design-review audits, JLCPCB part search, Freerouting, reference circuits, and a full manufacturing export pipeline.” Concrete operations include place/wire schematic components; place/move/rotate/route footprints over KiCad IPC; ERC/DRC/connectivity/decoupling/power/BOM audits; Gerber/drill/BOM/PnP/3D/PDF exports; JLCPCB search; live viewer.
- **Actual KiCad interface:** native `.kicad_sch` S-expression engine with atomic writes; KiCad 10 IPC API for live PCB changes and undo; `kicad-cli` for checks/exports.
- **Evidence:** v0.2.0 release; 11 test-path matches in checkout; current GitHub workflows; README explicitly labels beta and Linux as CI-tested but not platform-QA’d.
- **Last update/version:** commit 2026-07-24; v0.2.0 published 2026-07-18.
- **License:** AGPL-3.0; commercial licenses offered.
- **Installability / pain:** release binary or Cargo; **Medium** (KiCad 10 + IPC/open board for PCB tools; license decision).
- **Verdict:** **SOLID (BETA)** — top full-MCP evaluation candidate; broadest credible modern architecture.

### 2. KiCAD-MCP-Server (mixelpixx)

- **URL/repo:** https://github.com/mixelpixx/KiCAD-MCP-Server
- **Type:** MCP (TypeScript frontend + Python KiCad backend)
- **Real install (README, Linux):** `git clone https://github.com/mixelpixx/KiCAD-MCP-Server.git && cd KiCAD-MCP-Server && npm install && pip3 install -r requirements.txt && npm run build`
- **Tools exposed:** README says **122 tools across 12 categories**, with 22 direct tools and 100 routed tools. Verbatim categories/functions include project management; board operations; 16 component tools; 13 routing tools; 27 schematic tools; 8 DRC/rule tools; 8 exports; library/symbol/autoroute tools. Examples: `create_project`, `add_schematic_component`, `add_schematic_connection`, `sync_schematic_to_board`, `route_pad_to_pad`, `run_erc`, `run_drc`, `export_gerber`, `export_bom`, `autoroute`.
- **Actual KiCad interface:** SWIG/`pcbnew` backend with experimental official IPC fallback; direct schematic S-expression manipulation; `kicad-cli` for checks/exports.
- **Evidence:** extensive examples and 114 test-path matches; v2.4.0 fixes verified against real `kicad-cli` 10.0. README honestly documents historical broken schematic workflow and experimental IPC. Maintainer says Konnect is where new development happens.
- **Last update/version:** commit 2026-07-24; v2.4.0 published 2026-07-22.
- **License:** MIT.
- **Installability / pain:** npm + pip + KiCad bindings; **High**.
- **Verdict:** **SOLID** — real and feature-rich, but choose Konnect for a new eval unless MIT licensing is decisive.

### 3. KiCad MCP Pro

- **URL/repo:** https://github.com/oaslananka/kicad-mcp-pro
- **Type:** MCP + dashboard/desktop app + bundled Claude/Codex/Cursor/OpenCode skills
- **Real install (README):** `uvx kicad-mcp-pro --transport stdio` (or `npx kicad-mcp-pro --help`; Claude integration uses `claude mcp add --transport stdio --scope project kicad -- uvx kicad-mcp-pro`).
- **Tools exposed:** default profile has **24 read-only review tools**; full expert catalog claims **377 tools**. README’s verbatim scope is “schematic, PCB, validation, DFM, and manufacturing export automation”; profiles gate review/build/release/expert. Agent skills cover `kicad-design-review`, `pcb-design`, `drc-check`, `fabrication-output`, and `schematic-review`.
- **Evidence:** PyPI API returned v3.28.0; 345 test-path matches; docs, generated tool catalog, Docker metadata, CI and releases. Clean install failed on this host because current releases require **Python >=3.13** while host Python is 3.11; `uvx` was not installed. Latest GitHub CI run was failing at inspection time, so claims were not independently exercised.
- **Last update/version:** commit 2026-07-25; v3.28.0 / GUI release 2026-07-22.
- **License:** MIT.
- **Installability / pain:** PyPI/npm/Docker/desktop, but Python 3.13 floor; **Medium–High**.
- **Verdict:** **RISKY** for immediate harness use — unusually comprehensive and professionally documented, but huge surface, current CI failure, and host incompatibility increase eval noise.

### 4. Seeed Studio KiCad MCP Server

- **URL/repo:** https://github.com/Seeed-Studio/kicad-mcp-server
- **Type:** Python MCP
- **Real install (README):** `pip install -e .`; full mode installs `fastmcp` and the repo into KiCad’s bundled Python. Claude: `claude mcp add kicad -s user -- python -m kicad_mcp_server`.
- **Tools exposed (verbatim):** `list_schematic_components`, `list_schematic_nets`, `get_schematic_info`, `search_symbols`, `get_symbol_details`; PCB footprint/statistics/tracks/net/SI/PI analysis; `generate_netlist`, connection tracing; `run_erc`, `run_drc`, `detect_pin_conflicts`; `create_kicad_project`, `add_component_from_library`, `add_wire`, `add_label`, `setup_pcb_layout`, `export_gerber`.
- **Actual KiCad interface:** `pcbnew` for full PCB analysis, `kicad-cli` ERC/DRC/netlist, text fallback and S-expression schematic editing.
- **Evidence:** README has concrete workflows; 23 test-path matches. It explicitly says editing is experimental, wire connectivity may be imperfect, and recommends GUI for design work.
- **Last update/version:** commit 2026-05-22; no GitHub release.
- **License:** **No license detected** (README says MIT, but GitHub API and checkout had no LICENSE); legally ambiguous.
- **Installability / pain:** source pip install, KiCad-Python coupling; **Medium–High**.
- **Verdict:** **RISKY** — credible for analysis/validation, not a preferred end-to-end editing eval.

### 5. Netlist Studio kicad-mcp

- **URL/repo:** https://github.com/Netlist-Studio/kicad-mcp
- **Type:** KiCad 9 IPC MCP
- **Real install (README):** `git clone` + `uv sync`, then `claude mcp add kicad -- uv --directory /path/to/kicad-mcp run kicad-mcp`.
- **Tools exposed (verbatim):** `ping`, `get_version`, `get_board_info`, `get_footprints`, `get_nets`, `get_tracks`, `get_vias`, `get_zones`, `get_board_outline`, `get_component_connections`, `move_footprint`, `rotate_footprint`, `batch_move_footprints`, `create_track`, `remove_items_by_id`, `refill_zones`, `save_board`.
- **Actual KiCad interface:** official local KiCad IPC socket; live edits and undo commits.
- **Evidence:** README has natural-language examples, but badge and text say experimental; install example incorrectly clones `your-org/kicad-mcp`; zero test-path matches and no release.
- **Last update/version:** commit 2026-02-25; no release.
- **License:** MIT.
- **Installability / pain:** uv + running KiCad 9/open board; **Medium**.
- **Verdict:** **RISKY** — refreshingly small live-PCB surface, but under-tested and installation documentation is stale.

### 6. MCP KiCAD Schematic API

- **URL/repo:** https://github.com/circuit-synth/mcp-kicad-sch-api
- **Type:** schematic-only MCP wrapper
- **Advertised install:** `pip install mcp-kicad-sch-api`; Claude: `claude mcp add mcp-kicad-sch-api /path/to/venv/bin/mcp-kicad-sch-api`.
- **Tools exposed (verbatim):** `create_schematic`, `add_component`, `search_components`, `add_wire`, `add_hierarchical_sheet`, `add_sheet_pin`, `add_hierarchical_label`, `list_components`, `get_schematic_info`.
- **Actual KiCad interface:** wraps `kicad-sch-api` to read/write schematic S-expressions; no PCB layout/DRC/Gerber surface.
- **Evidence:** seven test-path matches and a v0.1.0 release, but live PyPI API returned 404 and a clean `pip install mcp-kicad-sch-api` returned “No matching distribution found.” Source install might still work, but the README’s primary command does not.
- **Last update/version:** commit 2025-08-20; v0.1.0 published 2025-08-19.
- **License:** MIT.
- **Installability / pain:** advertised PyPI path broken; **High** until installed from source and tested.
- **Verdict:** **DEAD as published** — reachable source, broken published install, narrow and stale.

### 7. lamaalrajih/kicad-mcp

- **URL/repo:** https://github.com/lamaalrajih/kicad-mcp
- **Type:** read/analysis-focused MCP
- **Real install (README):** `git clone https://github.com/lamaalrajih/kicad-mcp.git && cd kicad-mcp && make install`, then `python main.py` and configure that absolute interpreter/script in the MCP client.
- **Tools exposed:** README describes project listing/opening, PCB/schematic analysis, netlist extraction, BOM generation, DRC/history, PCB thumbnails, and circuit-pattern recognition. It does **not** promise schematic capture or PCB layout editing.
- **Evidence:** six test-path matches and detailed docs. It is the second-most-starred result, but no release and no commits since 2025-10.
- **Last update/version:** 2025-10-17; no release.
- **License:** MIT.
- **Installability / pain:** source + make + uv + KiCad; **Medium**.
- **Verdict:** **RISKY** — real, but stale and primarily inspection/launch rather than PCB construction.

### 8. kicad-jlcpcb

- **URL/repo:** https://github.com/BeckhamLabsLLC/kicad-jlcpcb
- **Type:** Claude Code plugin + skill + 13-tool MCP
- **Real install (README):** clone repo, create venv, `pip install -e ".[dev]"`; register local Claude marketplace/plugin and point `.mcp.json` at the venv’s `kicad-jlcpcb` executable.
- **Tools exposed (verbatim):** `detect_kicad`, `create_project`, `load_project`, `session_resume`, `lcsc_search`, `lcsc_resolve_bom`, `fetch_part_library`, `part_pin_map`, `sch_generate`, `sch_run_erc`, `pcb_generate`, `easyeda_handoff`, `package_for_jlcpcb`.
- **Actual KiCad interface:** `kicad-cli`, `pcbnew`, own S-expression writer; sources LCSC/EasyEDA data and emits a wired `.kicad_pcb`.
- **Evidence:** README says 212 tests, repo contains tests and a complete soil-sensor walkthrough; latest workflows succeeded. It explicitly does **not** autoroute, produce beautiful placement, or currently perform DRC; final routing is an EasyEDA browser handoff.
- **Last update/version:** 2026-04-20; no release/PyPI package.
- **License:** MIT.
- **Installability / pain:** source venv + KiCad + external EasyEDA/LCSC; **High**.
- **Verdict:** **RISKY** for a KiCad-only eval — genuine and tested, but the successful path exits KiCad for EasyEDA.

## Published agent skills / CLI wrappers

### 9. mash/kicad-skills

- **URL/repo:** https://github.com/mash/kicad-skills
- **Type:** Claude Code plugin/skills + `kicad-tool` CLI wrapper (not MCP)
- **Real install (README):** Claude commands `/plugin marketplace add mash/kicad-skills` and `/plugin install kicad-skills@kicad-skills`; direct bootstrap uses `pipx install git+https://github.com/mash/kicad-skills.git` or `uv tool install ...`.
- **Tool surface (verbatim CLI domains):** `sch render-region/inspect/erc/netlist/validate`; schematic symbol/pin/net/region/wire/label/library queries and symbol/wire/label/junction edits; `pcb drc/validate/render-region/sync`; footprint/pad/net/region/zone/via queries; footprint/zone/via edits. Mutations support `--dry-run`; structured JSON is available.
- **Evidence:** clean venv install from GitHub succeeded and `kicad-tool --help` returned domains `sch`, `pcb`, `mod`; 27 test-path matches. README documents safety boundaries and validation workflow.
- **Last update/version:** commit 2026-06-06; no tagged release.
- **License:** **No LICENSE file detected** — significant legal ambiguity despite public source.
- **Installability / pain:** GitHub pipx/uv/plugin; requires `kicad-cli` for validation/render; **Low–Medium**.
- **Verdict:** **SOLID technically / RISKY legally** — best controlled skill baseline; ask maintainer to add an explicit license before redistribution.

### 10. kicad-happy

- **URL/repo:** https://github.com/aklofas/kicad-happy
- **Type:** cross-agent skill suite + pure-Python analyzers (read/review, not layout MCP)
- **Real install (README):** Claude plugin marketplace commands; Codex built-in `$skill-installer`; or clone and symlink `skills/*` into `~/.codex/skills/` / `~/.claude/skills/`.
- **Tool surface:** parse/analyze KiCad 5–10 schematics, PCBs, Gerbers and PDF schematics; structured analyzers for components/nets/subcircuits, PCB routing/thermal/DFM, Gerbers/drills; design review, SPICE, EMC, datasheets, BOM and fab workflows. README explicitly describes pure Python scripts requiring no KiCad installation.
- **Evidence:** rich example reports, tests, successful current CI, v2.1.0 stable release; listed live on skills marketplace search.
- **Last update/version:** commit 2026-07-24; v2.1.0 published 2026-07-17.
- **License:** MIT.
- **Installability / pain:** plugin/symlink, zero required Python dependencies; **Low**.
- **Verdict:** **SOLID** for analysis/review; not eligible as the sole tool in a create/layout eval because it intentionally analyzes rather than edits.

### 11. Circuit Weaver (`mattpainter701/kicad_automations`)

- **URL/repo:** https://github.com/mattpainter701/kicad_automations
- **Type:** PyPI CLI + installable Claude/Codex/OpenCode skill bundle
- **Real install (README):** `pip install circuit-weaver`, then `circuit-weaver install-skills`.
- **Tool surface:** design wizard and validated schematic hierarchy generation; import/analyze existing KiCad/Gerber designs; placement optimizer/viewer; strict placement import; validation evidence, manufacturing artifacts and agent workflows. It generates schematics but requires KiCad “Update PCB from Schematic” for the authoritative electrical PCB.
- **Evidence:** PyPI API returned v0.32.1; clean venv install succeeded and `circuit-weaver --version` returned `0.32.1`; 100 test-path matches. Latest inspected “Validate Designs” workflow was failing.
- **Last update/version:** commit 2026-07-10; v0.32.1 published 2026-07-10.
- **License:** MIT.
- **Installability / pain:** normal PyPI + built-in skill installer; **Low–Medium**.
- **Verdict:** **SOLID/RISKY boundary** — real and highly testable, but not direct full PCB editing and current workflow failure reduce confidence for the first two evals.

### 12. electronics-agent-kit KiCad CLI skill

- **URL/repo:** https://github.com/o2scale/electronics-agent-kit/tree/main/.agent/skills/kicad-cli
- **Type:** reference skill / direct `kicad-cli` wrapper instructions
- **Real install:** clone/copy `.agent/skills/kicad-cli/`; no package install is defined. Runtime is KiCad’s own `kicad-cli`.
- **Tool surface (verbatim command families):** schematic netlist/BOM/PDF/SVG/ERC; PCB DRC/Gerber/drill/PnP/STEP/VRML/PDF/SVG/DXF; footprint SVG/upgrade; symbol SVG.
- **Evidence:** concrete copy-paste KiCad 8 commands, but no tests, no release, and the skill is documentation rather than a structured tool server.
- **Last update/version:** repository commit 2026-02-03; no release.
- **License:** MIT.
- **Installability / pain:** copy skill + install KiCad; **Low**.
- **Verdict:** **RISKY** — useful zero-abstraction baseline, but weak as a separately attributable integration.

## Registry and market findings

- **Official MCP servers repo:** live tree search found **0 KiCad paths**.
- **Glama:** live search returned at least 20 KiCad listings, including the Seeed, mixelpixx, oaslananka, ProductOfAmerica, SpectraSynq and various zero-star repos. This confirms discoverability, not operability.
- **skills.sh:** search endpoint was reachable but its initial server payload exposed no result records (client-rendered); no claim was inferred from it.
- **skills marketplace (`skillsmp.com`):** live search exposed `aklofas/kicad-happy`, five Konnect KiCad skills, oaslananka review skills and `operating-kicad-eda` among results.
- **GitHub skill search:** additionally found project-local or registry-mirrored KiCad skills in `PolyKybd`, `elixpo/oreo`, `telagod/code-abyss`, `mash/kicad-skills`, `o2scale/electronics-agent-kit`, `BeckhamLabsLLC/kicad-jlcpcb`, and others. Project-local one-off prompts and mirrors were not promoted to full candidates unless they had their own installation story and executable KiCad surface.

## Exclusions and cautionary long tail

Live GitHub search also found many currently reachable repos such as `blwfish/kicad-mcp`, `Valxyria/kicad-mcp-pro`, `Huaqiu-Electronics/kicad-mcp`, `Finerestaurant/kicad-mcp-python`, `ProductOfAmerica/mcp-server-kicad`, `salitronic/eda-agent`, `SpectraSynq/mcp-kicad-cli`, `antonmadto/kicad-mcp`, and numerous zero-star 2026 forks/experiments. They are **real repositories**, but the time-box did not support cloning and independently validating every fast-moving near-duplicate. They are therefore **unrated, not endorsed, and not claimed dead**. Re-run discovery immediately before expanding the eval matrix.

`Huaqiu-Electronics/kicad-mcp-server` is archived and therefore not a current candidate. Repositories about chips named MCP23017/MCP2515 were excluded as false positives.

## Picked-two test plan

1. **mash/kicad-skills:** run deterministic fixture tasks (query net, move footprint/symbol, add wire/via/zone, dry-run, ERC/DRC, render, validate). Score file validity, preservation of unrelated S-expressions/UUIDs, validation accuracy, and agent tool efficiency.
2. **Konnect:** run the same fixture intent through MCP plus one end-to-end creation/export task. Score live IPC correctness/undo, schematic-to-PCB sync, routing outcome, ERC/DRC, Gerber/BOM/PnP output, and tool-call/context cost.

Keep KiCad/version/container constant and do not let Konnect’s bundled skills leak into the mash arm. Record exact commit/release because both projects are moving rapidly.
