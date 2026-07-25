# mixelpixx/Konnect — eval arm

**Repo:** https://github.com/mixelpixx/Konnect
**Type:** MCP + native KiCad 10 plugin + six bundled agent skills
**Install:** download `konnect-pcm-v<version>-<platform>.zip` from GitHub releases, then KiCad 10 → Plugin and Content Manager → Install from File. Or `cargo build --release -p konnect`.
**License:** AGPL-3.0; commercial licenses offered
**Tool surface:** **185 tools across 18 on-demand toolsets**: schematic capture, PCB layout/routing, ERC/DRC, design-review audits, JLCPCB part search, Freerouting, gerber/drill/BOM/PnP/3D/PDF exports.
**Last update:** 2026-07-24; v0.2.0 published 2026-07-18

## Eval role
This is the **full live-MCP arm**. Compared against mash/kicad-skills (file/CLI baseline).

## How to use from the agent
```bash
# Claude:
claude mcp add kicad -- /path/to/konnect
# Codex:
# Edit ~/.codex/config.toml to add the MCP server
# Cursor:
# Edit ~/.cursor/mcp.json to add the server
```

## Eval scoring dimensions
- Live IPC correctness (does it actually edit the open board?)
- Schematic-to-PCB sync
- Routing outcome
- ERC/DRC
- Gerber/BOM/PnP output
- Tool-call/context cost (relative to mash arm)
