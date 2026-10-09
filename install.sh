#!/usr/bin/env bash
# ==============================================================================
# Magic Suite — installer for bunny's MTGA Linux toolchain
# Components: rhystic-tracker, mtga-draft-tool, mtga-linux-exporter, mtg-mcp
# MIT (c) 2026 Balthazzahr
# ==============================================================================
set -euo pipefail

SUITE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPONENTS_DIR="$SUITE_DIR/components"

BIN_DIR="$HOME/.local/bin"
DESKTOP_DIR="$HOME/.local/share/applications"
ICON_DIR="$HOME/.local/share/icons/hicolor/512x512/apps"
CONFIG_DIR="$HOME/.config/magic-suite"

ALL_COMPONENTS=(rhystic-tracker mtga-draft-tool mtga-linux-exporter mtg-mcp)

ASSUME_YES=0
DO_LIST=0
DO_UNINSTALL=0

# ---- colors (tty fallback) ---------------------------------------------------
if [ -t 1 ]; then
    C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'
    C_BLUE=$'\033[34m'; C_BOLD=$'\033[1m'; C_RESET=$'\033[0m'
else
    C_GREEN=""; C_YELLOW=""; C_RED=""; C_BLUE=""; C_BOLD=""; C_RESET=""
fi

info()  { echo "${C_BLUE}==>${C_RESET} $*"; }
ok()    { echo "${C_GREEN}  ok${C_RESET} $*"; }
warn()  { echo "${C_YELLOW}  !!${C_RESET} $*" >&2; }
err()   { echo "${C_RED}  xx${C_RESET} $*" >&2; }
step()  { echo; echo "${C_BOLD}--- $* ---${C_RESET}"; }

cleanup() { :; }   # no temp state to roll back; individual steps are idempotent
trap cleanup EXIT

usage() {
    cat <<EOF
Usage: ./install.sh [options] [component ...]

Options:
  --yes, --all   Install all components without prompting
  --list         List available components and their detection status
  --uninstall    Remove everything the suite installed
  -h, --help     This help

With no options, asks y/N per component.
Components: ${ALL_COMPONENTS[*]}
EOF
}

# ---- arg parsing -------------------------------------------------------------
SELECTED=()
while [ $# -gt 0 ]; do
    case "$1" in
        --yes|--all|-y) ASSUME_YES=1 ;;
        --list)         DO_LIST=1 ;;
        --uninstall)    DO_UNINSTALL=1 ;;
        -h|--help)      usage; exit 0 ;;
        *)              SELECTED+=("$1") ;;
    esac
    shift
done

component_present() { [ -d "$COMPONENTS_DIR/$1" ]; }

detect_status() {
    case "$1" in
        rhystic-tracker)
            if [ -x "$COMPONENTS_DIR/rhystic-tracker/rhystic-tracker" ]; then
                echo "ready (prebuilt binary found)"
            else
                echo "NO BINARY — install will be skipped"
            fi ;;
        mtga-draft-tool)
            if [ -f "$COMPONENTS_DIR/mtga-draft-tool/main.py" ]; then
                echo "ready (source)"
            else
                echo "MISSING source"
            fi ;;
        mtga-linux-exporter)
            if [ -x "$COMPONENTS_DIR/mtga-linux-exporter/mtg-fetch" ]; then
                echo "ready"
            else
                echo "MISSING mtg-fetch"
            fi ;;
        mtg-mcp)
            if [ -f "$COMPONENTS_DIR/mtg-mcp/server.py" ]; then
                echo "ready"
            else
                echo "MISSING server.py"
            fi ;;
    esac
}

if [ "$DO_LIST" -eq 1 ]; then
    echo "Magic Suite components (in $COMPONENTS_DIR):"
    for c in "${ALL_COMPONENTS[@]}"; do
        if component_present "$c"; then
            printf '  %-22s %s\n' "$c" "$(detect_status "$c")"
        else
            printf '  %-22s %s\n' "$c" "NOT PACKAGED"
        fi
    done
    exit 0
fi

# ---- uninstall ---------------------------------------------------------------
if [ "$DO_UNINSTALL" -eq 1 ]; then
    step "Uninstalling Magic Suite"
    rm -f "$BIN_DIR/mtg-fetch" \
          "$BIN_DIR/mtga-draft-tool" \
          "$BIN_DIR/rhystic-tracker" \
          "$DESKTOP_DIR/mtga-draft-tool.desktop" \
          "$DESKTOP_DIR/rhystic-tracker.desktop" \
          "$ICON_DIR/rhystic-tracker.png"
    ok "removed binaries / launchers / desktop entries"
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        ok "removed $CONFIG_DIR (venvs, copied sources, mtg-mcp)"
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    echo
    ok "Magic Suite uninstalled."
    exit 0
fi

# ---- pick components ---------------------------------------------------------
if [ "${#SELECTED[@]}" -eq 0 ]; then
    SELECTED=("${ALL_COMPONENTS[@]}")
fi

TO_INSTALL=()
for c in "${SELECTED[@]}"; do
    if ! component_present "$c"; then
        warn "component '$c' not packaged in this suite — skipping"
        continue
    fi
    if [ "$ASSUME_YES" -eq 1 ]; then
        TO_INSTALL+=("$c")
    else
        read -r -p "Install ${C_BOLD}$c${C_RESET} ($(detect_status "$c"))? [y/N] " ans
        case "$ans" in [yY]|[yY][eE][sS]) TO_INSTALL+=("$c") ;; *) info "skipping $c" ;; esac
    fi
done

mkdir -p "$BIN_DIR" "$DESKTOP_DIR" "$ICON_DIR" "$CONFIG_DIR"

SUMMARY_OK=(); SUMMARY_FAIL=(); SUMMARY_SKIP=()

# ==============================================================================
install_rhystic_tracker() {
    step "Rhystic Tracker"
    local comp="$COMPONENTS_DIR/rhystic-tracker"
    if [ ! -x "$comp/rhystic-tracker" ]; then
        warn "no prebuilt binary at $comp/rhystic-tracker — skipping"
        SUMMARY_SKIP+=("rhystic-tracker (no binary)"); return 0
    fi
    # Delegate to the tracker's own installer; it picks up the binary and
    # icons/icon.png sitting next to it.
    "$comp/install.sh"
    # verify
    if [ -x "$BIN_DIR/rhystic-tracker" ] && [ -f "$DESKTOP_DIR/rhystic-tracker.desktop" ]; then
        ok "verified: $BIN_DIR/rhystic-tracker + desktop entry"
        SUMMARY_OK+=("rhystic-tracker")
    else
        err "verification failed for rhystic-tracker"
        SUMMARY_FAIL+=("rhystic-tracker"); return 1
    fi
}

install_mtga_draft_tool() {
    step "MTGA Draft Tool (unrealities fork, v4.23)"
    local comp="$COMPONENTS_DIR/mtga-draft-tool"
    local dest="$CONFIG_DIR/mtga-draft-tool"
    local venv="$CONFIG_DIR/mtga-draft-tool-venv"

    # The fork requires Python >=3.12,<3.15 (pyproject.toml). pynput pulls in
    # evdev, a C extension, so the interpreter must ship its headers (Python.h).
    local py=""
    local cand
    for cand in python3.14 python3.13 python3.12 python3; do
        if command -v "$cand" >/dev/null 2>&1; then
            if "$cand" -c '
import sys, sysconfig, os
ok = (3,12) <= sys.version_info[:2] < (3,15)
ok = ok and os.path.exists(os.path.join(sysconfig.get_paths()["include"], "Python.h"))
raise SystemExit(0 if ok else 1)' 2>/dev/null; then
                py="$cand"; break
            fi
        fi
    done
    if [ -z "$py" ]; then
        err "no Python >=3.12,<3.15 with dev headers (Python.h) found."
        err "Tried python3.14/3.13/3.12/python3. Install one (e.g. 'sudo pacman -S python'"
        err "or 'uv python install 3.12') and re-run."
        SUMMARY_FAIL+=("mtga-draft-tool (no suitable python)"); return 1
    fi
    info "using interpreter: $py ($($py --version 2>&1))"
    if ! "$py" -c 'import tkinter' 2>/dev/null; then
        warn "tkinter not importable for $py — the GUI needs it (Arch: 'sudo pacman -S tk')."
    fi

    info "copying source to $dest"
    rm -rf "$dest"
    mkdir -p "$dest"
    (cd "$comp" && tar cf - .) | (cd "$dest" && tar xf -)

    info "creating venv at $venv"
    rm -rf "$venv"
    "$py" -m venv "$venv"
    info "installing dependencies (pip install . — this can take a few minutes)"
    "$venv/bin/pip" install --quiet --upgrade pip
    "$venv/bin/pip" install --quiet "$dest"

    cat > "$BIN_DIR/mtga-draft-tool" <<EOF
#!/usr/bin/env bash
exec "$venv/bin/python" "$dest/main.py" "\$@"
EOF
    chmod +x "$BIN_DIR/mtga-draft-tool"

    cat > "$DESKTOP_DIR/mtga-draft-tool.desktop" <<EOF
[Desktop Entry]
Name=MTGA Draft Tool
GenericName=MTG Arena Draft Assistant
Comment=Draft helper for MTG Arena using 17Lands data
Exec=$BIN_DIR/mtga-draft-tool
Terminal=false
Type=Application
Categories=Game;Utility;
Keywords=mtg;magic;arena;draft;17lands;
EOF

    # verify: venv exists, deps importable, launcher executable
    if [ -x "$venv/bin/python" ] \
        && "$venv/bin/python" -c 'import numpy, PIL, pydantic, requests, ttkbootstrap' 2>/dev/null \
        && [ -x "$BIN_DIR/mtga-draft-tool" ]; then
        ok "verified: venv deps import, launcher at $BIN_DIR/mtga-draft-tool"
        SUMMARY_OK+=("mtga-draft-tool")
    else
        err "verification failed for mtga-draft-tool"
        SUMMARY_FAIL+=("mtga-draft-tool"); return 1
    fi
}

install_mtga_linux_exporter() {
    step "mtga-linux-exporter (mtg-fetch)"
    local comp="$COMPONENTS_DIR/mtga-linux-exporter"
    local dest="$CONFIG_DIR/mtga-linux-exporter"
    if [ ! -x "$comp/mtg-fetch" ]; then
        err "mtg-fetch missing in suite copy"; SUMMARY_FAIL+=("mtga-linux-exporter"); return 1
    fi
    # copy (not symlink into the suite dir) so moving the suite doesn't break the install
    rm -rf "$dest"
    mkdir -p "$dest"
    (cd "$comp" && tar cf - .) | (cd "$dest" && tar xf -)
    ln -sf "$dest/mtg-fetch" "$BIN_DIR/mtg-fetch"
    if [ -x "$BIN_DIR/mtg-fetch" ] && "$BIN_DIR/mtg-fetch" --help >/dev/null 2>&1; then
        ok "verified: mtg-fetch --help runs ($BIN_DIR/mtg-fetch -> $dest/mtg-fetch)"
        SUMMARY_OK+=("mtga-linux-exporter")
    else
        err "verification failed for mtga-linux-exporter"
        SUMMARY_FAIL+=("mtga-linux-exporter"); return 1
    fi
}

install_mtg_mcp() {
    step "mtg-mcp (MCP server)"
    local comp="$COMPONENTS_DIR/mtg-mcp"
    local dest="$CONFIG_DIR/mtg-mcp"
    mkdir -p "$dest"
    cp -f "$comp/server.py" "$comp/run.sh" "$dest/"
    chmod +x "$dest/run.sh"
    if [ -f "$dest/server.py" ] && [ -x "$dest/run.sh" ]; then
        ok "installed to $dest"
        SUMMARY_OK+=("mtg-mcp")
    else
        err "verification failed for mtg-mcp"
        SUMMARY_FAIL+=("mtg-mcp"); return 1
    fi
    cat <<EOF

  MCP registration snippet — point your client at:
    command: $dest/run.sh

  kimi-code (~/.config/kimi-code/mcp.json):
    { "mcpServers": { "mtg": { "command": "$dest/run.sh" } } }

  crush (crushrc / crush.json):
    { "mcp": { "mtg": { "type": "stdio", "command": "$dest/run.sh" } } }

  Prerequisite: MTGJSON AllPrintings.sqlite (free account at https://mtgjson.com)
  expected at: /home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite
EOF
}

for c in "${TO_INSTALL[@]}"; do
    case "$c" in
        rhystic-tracker)     install_rhystic_tracker     || true ;;
        mtga-draft-tool)     install_mtga_draft_tool     || true ;;
        mtga-linux-exporter) install_mtga_linux_exporter || true ;;
        mtg-mcp)             install_mtg_mcp             || true ;;
        *) warn "unknown component '$c' — skipping" ;;
    esac
done

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi

# ==============================================================================
step "Summary"
[ "${#SUMMARY_OK[@]}"   -gt 0 ] && ok   "installed: ${SUMMARY_OK[*]}"
[ "${#SUMMARY_SKIP[@]}" -gt 0 ] && warn "skipped:   ${SUMMARY_SKIP[*]}"
[ "${#SUMMARY_FAIL[@]}" -gt 0 ] && err  "failed:    ${SUMMARY_FAIL[*]}"

cat <<EOF

${C_BOLD}Post-install notes:${C_RESET}
  * mtga-linux-exporter: memory scanning needs ptrace relaxed:
        sudo sysctl kernel.yama.ptrace_scope=0
    (persist: echo 'kernel.yama.ptrace_scope=0' | sudo tee /etc/sysctl.d/60-mtg-fetch.conf)
  * MTGA Draft Tool: in MTG Arena enable
        Options -> Account -> Detailed Logs (Plugin Support)
    then restart Arena before drafting.
  * mtg-mcp: requires MTGJSON AllPrintings.sqlite (free MTGJSON account) at
        /home/bunny/Kimi/scratch/mtg/AllPrintings.sqlite
  * Rhystic Tracker + Draft Tool attach to Steam/Proton MTGA at:
        ~/.local/share/Steam/steamapps/common/MTGA
EOF

[ "${#SUMMARY_FAIL[@]}" -eq 0 ]
