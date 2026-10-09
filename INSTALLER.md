# INSTALLER.md — Magic Suite, step-by-step for an AI agent

Exact procedure to install the Magic Suite on any FHS-compliant Linux (tested on Fedora)
machine. Run everything as the unprivileged user; only the ptrace sysctl
uses sudo. Suite root assumed: `/home/bunny/Kimi/projects/magic-suite`.

The supported, preferred path is simply:

```bash
cd /home/bunny/Kimi/projects/magic-suite
./install.sh --yes        # or omit --yes for per-component y/N prompts
```

The steps below document exactly what the installer does, per component, with
verification and rollback, in case you need to do or debug them manually.

## 0. Prerequisites (check all before starting)

```bash
# Steam/Proton MTGA present
ls ~/.local/share/Steam/steamapps/common/MTGA

# Python for the draft tool: needs >=3.12,<3.15, tkinter, AND dev headers
# (pynput's evdev dependency is a C extension compiled at install time)
python3 -c 'import sys; print(sys.version)'
python3 -c 'import tkinter'   # if this fails: sudo pacman -S tk
python3 -c 'import sysconfig, os; print(os.path.join(sysconfig.get_paths()["include"], "Python.h"))'
# if Python.h is missing for /usr/bin/python3 (some minimal distro splits),
# use a uv-managed interpreter instead, e.g.: uv python install 3.12

# uv for mtg-mcp
~/.local/bin/uv --version

# MTGJSON sqlite for mtg-mcp (free account at https://mtgjson.com required
# to download AllPrintings.sqlite — do NOT attempt to fetch it without one)
ls /home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite
```

XDG target dirs (created by the installer if missing):
`~/.local/bin`, `~/.local/share/applications`,
`~/.local/share/icons/hicolor/512x512/apps`, `~/.config/magic-suite`.

## 1. Rhystic Tracker

Prebuilt binary ships at `components/rhystic-tracker/rhystic-tracker`.
Delegate to its own installer:

```bash
/home/bunny/Kimi/projects/magic-suite/components/rhystic-tracker/install.sh
```

It installs: binary → `~/.local/bin/rhystic-tracker`, desktop entry →
`~/.local/share/applications/rhystic-tracker.desktop`, icon →
`~/.local/share/icons/hicolor/512x512/apps/rhystic-tracker.png`.

Verify:
```bash
test -x ~/.local/bin/rhystic-tracker && echo OK
test -f ~/.local/share/applications/rhystic-tracker.desktop && echo OK
```

Rollback:
```bash
rm -f ~/.local/bin/rhystic-tracker \
      ~/.local/share/applications/rhystic-tracker.desktop \
      ~/.local/share/icons/hicolor/512x512/apps/rhystic-tracker.png
```

## 2. MTGA Draft Tool (unrealities fork, v4.23)

Requires Python >=3.12,<3.15 with dev headers (`Python.h` — `evdev` compiles at
install time) and tkinter (see `components/mtga-draft-tool/pyproject.toml`).
Pick the first interpreter passing all checks, in order
`python3 python3.14 python3.13 python3.12` — **prefer the system python3**:
standalone/uv Python builds ship a Tk without fontconfig, which breaks UI
font rendering (falls back to X core fonts). If the app looks like Windows 95,
the venv was built against a standalone build; rebuild it against the system
interpreter. The app hardcodes the "Ubuntu" font family on Linux — install it
(`~/.local/share/fonts`) or any missing-font fallback will look wrong.

```bash
SUITE=/home/bunny/Kimi/projects/magic-suite
DEST=~/.config/magic-suite/mtga-draft-tool
VENV=~/.config/magic-suite/mtga-draft-tool-venv
PY=python3   # must satisfy >=3.12,<3.15

rm -rf "$DEST" "$VENV"   # idempotent reinstall: drop stale files first
mkdir -p ~/.config/magic-suite "$DEST"
(cd "$SUITE/components/mtga-draft-tool" && tar cf - .) | (cd "$DEST" && tar xf -)
"$PY" -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip
"$VENV/bin/pip" install "$DEST"     # poetry-core backend; installs numpy, Pillow, pydantic, pynput, requests, ttkbootstrap, numba, scipy
```

Launcher `~/.local/bin/mtga-draft-tool`:
```bash
cat > ~/.local/bin/mtga-draft-tool <<EOF
#!/usr/bin/env bash
exec "$VENV/bin/python" "$DEST/main.py" "\$@"
EOF
chmod +x ~/.local/bin/mtga-draft-tool
```

Desktop entry `~/.local/share/applications/mtga-draft-tool.desktop`:
```
[Desktop Entry]
Name=MTGA Draft Tool
GenericName=MTG Arena Draft Assistant
Comment=Draft helper for MTG Arena using 17Lands data
Exec=$HOME/.local/bin/mtga-draft-tool   # expand $HOME to the absolute path
Icon=mtga-draft-tool
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=mtg;magic;arena;draft;17lands;
```
The icon is `components/mtga-draft-tool/icons/17lands.png`, copied to
`~/.local/share/icons/hicolor/512x512/apps/mtga-draft-tool.png`.
```

Verify:
```bash
"$VENV/bin/python" -c 'import numpy, PIL, pydantic, requests, ttkbootstrap; print("deps OK")'
test -x ~/.local/bin/mtga-draft-tool && echo OK
```

Rollback:
```bash
rm -rf "$DEST" "$VENV" ~/.local/bin/mtga-draft-tool \
       ~/.local/share/applications/mtga-draft-tool.desktop
```

Post-install: in MTG Arena enable *Options → Account → Detailed Logs
(Plugin Support)* and restart Arena; the tool reads `Player.log`.
To auto-start Rhystic Tracker alongside MTGA, set Steam → MTGA →
Properties → Launch Options to
`GDK_BACKEND=wayland ~/.local/bin/rhystic-tracker & %command%`
(keep any existing options, such as an ultrawide mod's
`WINEDLLOVERRIDES`, in front of `%command%`).

## 3. mtga-linux-exporter (`mtg-fetch`)

Stdlib-only Python 3.10+, no pip needed. Install by copying, then symlink:

```bash
SUITE=/home/bunny/Kimi/projects/magic-suite
DEST=~/.config/magic-suite/mtga-linux-exporter
mkdir -p "$DEST"
(cd "$SUITE/components/mtga-linux-exporter" && tar cf - .) | (cd "$DEST" && tar xf -)
ln -sf "$DEST/mtg-fetch" ~/.local/bin/mtg-fetch
```

Verify:
```bash
mtg-fetch --help
mtg-fetch check --format json   # full check; needs MTGA running + ptrace relaxed
```

Rollback:
```bash
rm -f ~/.local/bin/mtg-fetch && rm -rf ~/.config/magic-suite/mtga-linux-exporter
```

Post-install (needs sudo, required before `collect` works):
```bash
sudo sysctl kernel.yama.ptrace_scope=0
# persist across reboots:
echo 'kernel.yama.ptrace_scope=0' | sudo tee /etc/sysctl.d/60-mtg-fetch.conf
```

## 4. mtg-mcp (MCP server)

```bash
SUITE=/home/bunny/Kimi/projects/magic-suite
DEST=~/.config/magic-suite/mtg-mcp
mkdir -p "$DEST"
cp "$SUITE/components/mtg-mcp/server.py" "$SUITE/components/mtg-mcp/run.sh" "$DEST/"
chmod +x "$DEST/run.sh"
```

Verify:
```bash
test -x ~/.config/magic-suite/mtg-mcp/run.sh && echo OK
ls /home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite   # prerequisite data file
```

Register with MCP clients, command = `~/.config/magic-suite/mtg-mcp/run.sh`:

- kimi-code, `~/.config/kimi-code/mcp.json`:
  `{ "mcpServers": { "mtg": { "command": "/home/bunny/.config/magic-suite/mtg-mcp/run.sh" } } }`
- crush, crushrc:
  `{ "mcp": { "mtg": { "type": "stdio", "command": "/home/bunny/.config/magic-suite/mtg-mcp/run.sh" } } }`

`run.sh` does `uv run --quiet --with 'mcp<2' python server.py`; the server opens
the MTGJSON sqlite read-only at the path hardcoded in `server.py`
(`/home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite`).

Rollback:
```bash
rm -rf ~/.config/magic-suite/mtg-mcp
```

## Full-suite rollback

```bash
/home/bunny/Kimi/projects/magic-suite/install.sh --uninstall
```

removes every file listed in the rollback sections above, plus
`~/.config/magic-suite` entirely.
