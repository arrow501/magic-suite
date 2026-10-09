#!/usr/bin/env bash
exec "$HOME/.local/bin/uv" run --quiet --with 'mcp<2' python "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")/server.py"
