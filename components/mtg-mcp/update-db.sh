#!/usr/bin/env bash
# Refresh the local MTGJSON AllPrintings.sqlite used by the mtg MCP server.
# Safe to run anytime; downloads to a temp file and swaps atomically.
set -euo pipefail

DB_DIR="${MTGJSON_DIR:-/home/bunny/.local/share/magic-suite}"
DB="$DB_DIR/AllPrintings.sqlite"
TMP="$DB.tmp.gz"

cd "$DB_DIR"
echo "Downloading AllPrintings.sqlite.gz from mtgjson.com ..."
curl -sfLO https://mtgjson.com/api/v5/AllPrintings.sqlite.gz -o "$TMP"

if [ -f "$DB" ]; then
    old_size=$(stat -c %s "$DB")
    cp -f "$DB" "$DB.bak"
else
    old_size=0
fi

gunzip -c "$TMP" > "$DB.tmp"
rm -f "$TMP"
mv -f "$DB.tmp" "$DB"

new_size=$(stat -c %s "$DB")
if [ "$new_size" -lt 100000000 ]; then
    echo "ERROR: new DB suspiciously small ($new_size bytes) — restoring backup" >&2
    [ -f "$DB.bak" ] && mv -f "$DB.bak" "$DB"
    exit 1
fi
rm -f "$DB.bak"
echo "Updated $DB ($old_size -> $new_size bytes)"
sqlite3 "$DB" "SELECT name, date FROM sets ORDER BY date DESC LIMIT 3;" 2>/dev/null || true
