# Magic Suite

bunny's MTG Arena Linux toolchain, bundled as one distributable directory.
Targets Linux (Arch/Omarchy) with MTG Arena running through Steam/Proton at
`~/.local/share/Steam/steamapps/common/MTGA`.

## Quick start

```bash
./install.sh            # interactive, asks y/N per component
./install.sh --yes      # install everything
./install.sh --list     # show components and detection status
./install.sh --uninstall
```

See `INSTALLER.md` for the same procedure written as exact steps for an AI agent.

## Components

| Component | Purpose | Upstream | License | Maintained? |
|---|---|---|---|---|
| **Rhystic Tracker** | Tauri GUI: real-time MTGA match/deck tracking, stats history | [Balthazzahr/Rhystic-Tracker](https://github.com/Balthazzahr/Rhystic-Tracker) | MIT © 2026 Balthazzahr | Yes — upstream by Balthazzahr, this is a fork |
| **MTGA Draft Tool** | Draft overlay using 17Lands card ratings (v4.23) | [unrealities/MTGA_Draft_17Lands](https://github.com/unrealities/MTGA_Draft_17Lands) | MIT © 2022 bstaple1 & 2024 unrealities | Yes — the unrealities fork is the actively maintained line; the original bstaple1 repo is abandoned |
| **mtga-linux-exporter** | `mtg-fetch` CLI: exports your Arena collection by scanning the running Proton process's memory; enriches via Scryfall | [IpastorSan/mtga-linux-exporter](https://github.com/IpastorSan/mtga-linux-exporter) | MIT © 2026 Ignacio Pastor | Yes |
| **mtg-mcp** | MCP server for AI deckbuilding: oracle text, legality, deck analysis over a local MTGJSON sqlite | Arrow (`tools/mtg-mcp`) | MIT © 2026 Arrow | Yes — Arrow's own |

Per-component license texts live in `LICENSES/`. Suite glue (installer,
launchers, mtg-mcp) is MIT © 2026 Arrow (see `LICENSE`).

## Layout

```
components/
  rhystic-tracker/      prebuilt binary + its install.sh + .desktop + icon
  mtga-draft-tool/      full source clone of the unrealities fork (no .git,
                        no PyInstaller binary)
  mtga-linux-exporter/  full tool (no .git)
  mtg-mcp/              server.py + run.sh
LICENSES/               per-component license texts
install.sh              interactive installer (XDG paths)
INSTALLER.md            step-by-step agent instructions
```

## Prerequisites

- **mtga-linux-exporter**: MTGA running via Proton; relaxed ptrace
  (`sudo sysctl kernel.yama.ptrace_scope=0`); Collection tab opened once in-game.
- **MTGA Draft Tool**: Python >=3.12,<3.15 with tkinter (Arch: `pacman -S tk`);
  Arena's *Options → Account → Detailed Logs (Plugin Support)* enabled.
- **mtg-mcp**: `uv`; MTGJSON `AllPrintings.sqlite` (free account at
  https://mtgjson.com) at `/home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite`.
- **MTGA Steam launch options** (Steam → MTGA → Properties → Launch Options),
  needed so trackers can read the log through Wine's winhttp:
  `WINEDLLOVERRIDES="winhttp=n,b" %command%`
- **Rhystic Tracker**: ships as a prebuilt binary, no build deps needed; its
  desktop entry launches with `GDK_BACKEND=wayland`.

## License fix note

The upstream `scratch/rhystic-tracker/LICENSE` had a defective copyright line
("Copyright (c) 2026 MIT"). The suite copy (`LICENSES/rhystic-tracker.LICENSE.txt`
and `components/rhystic-tracker/LICENSE`) corrects this to
"Copyright (c) 2026 Balthazzahr".

## Legal / data-usage notes

This is unofficial fan content. Magic: The Gathering, MTG Arena, and all card
names/images are © Wizards of the Coast. These tools are not produced by,
endorsed by, or affiliated with Wizards of the Coast.

- **17Lands** data (draft tool): respect 17Lands' usage terms; the tool
  downloads their public draft datasets.
- **Scryfall** (exporter `enrich`): uses the per-card API with local caching,
  honoring Scryfall's rate-limit guidance (50–100 ms between requests).
