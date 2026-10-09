#!/usr/bin/env python3
"""MTGA suite MCP for Kimi — card data, collection, and match tracking.

Data sources (all read-only):
- MTGJSON AllPrintings.sqlite: oracle text, legality, pool/deck search
- MTGA collection export (collection.json): ownership, deck craft cost
- Rhystic Tracker db: match history, deck stats
Tools are batch-first: pass lists, get back everything in one call.
"""
import contextlib
import json
import os
import re
import sqlite3

from mcp.server.fastmcp import FastMCP

DB_PATH = "/home/bunny/.local/share/magic-suite/AllPrintings.sqlite"

mcp = FastMCP("mtga-deckbuilder")


def db():
    # contextlib.closing: sqlite3's own context manager commits but never
    # closes — in a long-lived server that leaks an fd per tool call
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return contextlib.closing(conn)


def _resolve_name(conn, name: str) -> str | None:
    """Exact -> case-insensitive -> substring match. Returns the canonical
    card name or None."""
    row = conn.execute(
        "SELECT name FROM cards WHERE name = ? LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        "SELECT name FROM cards WHERE name = ? COLLATE NOCASE LIMIT 1", (name,)
    ).fetchone()
    if row:
        return row[0]
    row = conn.execute(
        """SELECT name FROM cards WHERE name LIKE ? COLLATE NOCASE
           GROUP BY name ORDER BY length(name) LIMIT 1""",
        (f"%{name}%",),
    ).fetchone()
    return row[0] if row else None

@mcp.tool()
def cards_fulltext(names: list[str]) -> str:
    """Batch: full oracle text and stats for cards by name. Names are resolved
    fuzzily (exact -> case-insensitive -> substring); resolved names are shown.
    Returns the newest Standard-legal printing when possible, else newest overall.
    Output per card, one or two lines:
      Name | {cost} | type | rarity setcode | std/legal or --
      rules text (blank for vanilla)
    Unknown names: 'Name ?? not found'."""
    blocks = []
    with db() as conn:
        for name in names:
            resolved = _resolve_name(conn, name)
            if not resolved:
                blocks.append(f"{name} ?? not found")
                continue
            rows = conn.execute(
                """SELECT c.*, l.standard FROM cards c
                   LEFT JOIN cardLegalities l ON c.uuid = l.uuid
                   LEFT JOIN sets s ON c.setCode = s.code
                   WHERE c.name = ? AND (c.side IS NULL OR c.side = 'a')
                   ORDER BY (l.standard = 'Legal') DESC,
                            (s.type IN ('core', 'expansion')) DESC,
                            c.originalReleaseDate DESC""",
                (resolved,),
            ).fetchall()
            if not rows:
                blocks.append(f"{name} ?? not found")
                continue
            r = rows[0]
            head = " | ".join(x for x in (
                r["name"], r["manaCost"], r["type"],
                f'{r["rarity"]} {r["setCode"]}',
                "std" if r["standard"] == "Legal" else "--",
            ) if x)
            if resolved != name:
                head += f'  (resolved from "{name}")'
            pt = f'{r["power"]}/{r["toughness"]}' if r["power"] else ""
            body = "\n".join(x for x in (r["text"], pt) if x)
            blocks.append(f"{head}\n{body}" if body else head)
    return "\n\n".join(blocks)


@mcp.tool()
def legality(names: list[str], format: str = "standard") -> str:
    """Batch: legality per card name for a format column in cardLegalities
    (standard, modern, pioneer, commander, ...). A card is legal if ANY printing is.
    Names resolved fuzzily like cards_fulltext.
    Output: one line per card, 'L name' or '- name' (input order, L = legal)."""
    col = format.lower()
    if col not in ("standard", "pioneer", "modern", "legacy", "vintage",
                   "commander", "explorer", "historic", "alchemy", "brawl", "pauper"):
        return f"error: unknown format column {col}"
    lines = []
    with db() as conn:
        for name in names:
            resolved = _resolve_name(conn, name)
            if not resolved:
                lines.append(f"- {name} (not found)")
                continue
            row = conn.execute(
                f"""SELECT 1 FROM cards c JOIN cardLegalities l ON c.uuid = l.uuid
                    WHERE c.name = ? AND l.{col} = 'Legal' LIMIT 1""",
                (resolved,),
            ).fetchone()
            lines.append(f"{'L' if row else '-'} {resolved}")
    return "\n".join(lines)


def _search_filters(
    name_contains: str | None,
    text_regex: str | None,
    colors: str | None,
    identity: str | None,
    types: str | None,
    keyword: str | None,
    type_contains: str | None,
    rarity: str | None,
    max_mana_value: float | None,
) -> tuple[list[str], list]:
    """Shared WHERE-clause builder for search_cards / collection_search.
    colors: card colors are a subset of the given letters.
    identity: color identity is a subset of the given letters (brawl/commander).
    types: comma-separated tokens, all must appear in the type line
    (e.g. 'Legendary, Creature').
    keyword: keyword ability token (flying, trample, ...) matched against the
    card's keyword list, plus a rules-text fallback for older data."""
    where, args = ["(c.side IS NULL OR c.side = 'a')"], []
    if name_contains:
        where.append("c.name LIKE ?")
        args.append(f"%{name_contains}%")
    if text_regex:
        where.append("c.text REGEXP ?")
        args.append(text_regex)
    tokens = [t.strip() for t in (types or type_contains or "").split(",") if t.strip()]
    for t in tokens:
        where.append("c.type LIKE ?")
        args.append(f"%{t}%")
    if keyword:
        where.append("(c.keywords LIKE ? OR c.text LIKE ?)")
        args.extend([f"%{keyword}%", f"%{keyword}%"])
    if rarity:
        where.append("c.rarity = ?")
        args.append(rarity.lower())
    if max_mana_value is not None:
        where.append("c.manaValue <= ?")
        args.append(max_mana_value)
    if colors:
        excluded = [p for p in "WUBRG" if p not in set(colors.upper())]
        if excluded:
            where.append("(c.colors IS NULL OR c.colors = '' OR ("
                         + " AND ".join("c.colors NOT LIKE ?" for _ in excluded) + "))")
            args.extend(f"%{p}%" for p in excluded)
    if identity:
        excluded = [p for p in "WUBRG" if p not in set(identity.upper())]
        if excluded:
            where.append("(c.colorIdentity IS NULL OR c.colorIdentity = '' OR ("
                         + " AND ".join("c.colorIdentity NOT LIKE ?" for _ in excluded) + "))")
            args.extend(f"%{p}%" for p in excluded)
    return where, args


def _regexp(pattern, value):
    if value is None:
        return False
    try:
        return re.search(pattern, value) is not None
    except re.error:
        return False


@mcp.tool()
def search_cards(
    name_contains: str | None = None,
    text_regex: str | None = None,
    colors: str | None = None,
    identity: str | None = None,
    types: str | None = None,
    keyword: str | None = None,
    type_contains: str | None = None,
    rarity: str | None = None,
    max_mana_value: float | None = None,
    standard_only: bool = True,
    limit: int = 50,
) -> str:
    """Search the card pool.
    colors: letters from WUBRG, card colors are a subset of them.
    identity: letters from WUBRG, color identity subset (brawl/commander decks).
    types: comma tokens all present in the type line, e.g. 'Legendary, Creature'.
    keyword: keyword ability, e.g. 'flying'.
    text_regex: matched against rules text (e.g. 'Counter target' , '[Dd]iscard').
    Output: one line per card, alphabetically:
      Name {cost} type [rarity setcode] :: text"""
    where, args = _search_filters(name_contains, text_regex, colors, identity,
                                  types, keyword, type_contains, rarity,
                                  max_mana_value)
    if standard_only:
        where.append("l.standard = 'Legal'")
    # No GROUP BY here: bare columns under GROUP BY pick fields from arbitrary
    # printings of the same card. Fetch ranked printings and dedupe in Python,
    # same preference order as cards_fulltext.
    sql = f"""SELECT c.name, c.manaCost, c.type, c.text, c.rarity, c.setCode
              FROM cards c
              LEFT JOIN cardLegalities l ON c.uuid = l.uuid
              LEFT JOIN sets s ON c.setCode = s.code
              WHERE {' AND '.join(where)}
              ORDER BY c.name,
                       (l.standard = 'Legal') DESC,
                       (s.type IN ('core', 'expansion')) DESC,
                       c.originalReleaseDate DESC"""

    with db() as conn:
        conn.create_function("regexp", 2, _regexp)
        rows = conn.execute(sql, args).fetchall()
    seen: set[str] = set()
    lines = []
    for r in rows:
        if r["name"] in seen:
            continue
        seen.add(r["name"])
        lines.append(
            f'{r["name"]} {r["manaCost"] or ""} {r["type"]} [{r["rarity"]} {r["setCode"]}] :: {r["text"] or ""}'
            .replace("  ", " ").rstrip(" :"))
        if len(lines) >= limit:
            break
    return "\n".join(lines)


COLLECTION_PATH = "/home/bunny/.local/share/magic-suite/collection.json"

_collection_cache: dict = {"mtime": None, "by_name": {}}


def _collection() -> dict[str, int]:
    """Owned card counts summed across printings, keyed by canonical name.
    Reloads when the collection file changes; empty dict if absent."""
    try:
        mtime = os.path.getmtime(COLLECTION_PATH)
    except OSError:
        return {}
    if _collection_cache["mtime"] != mtime:
        try:
            with open(COLLECTION_PATH) as f:
                data = json.load(f)
            by_name: dict[str, int] = {}
            for c in data.get("cards", []):
                if c.get("name"):
                    by_name[c["name"]] = by_name.get(c["name"], 0) + c["count"]
            _collection_cache.update(mtime=mtime, by_name=by_name)
        except (json.JSONDecodeError, OSError):
            _collection_cache.update(mtime=mtime, by_name={})
    return _collection_cache["by_name"]


@mcp.tool()
def update_card_db() -> str:
    """Refresh the local MTGJSON card database (downloads AllPrintings.sqlite,
    ~700MB). Runs update-db.sh, which a human can also run directly from a
    shell. Takes a minute or two."""
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "update-db.sh")
    if not os.path.exists(script):
        return f"error: {script} not found"
    try:
        proc = subprocess.run(["bash", script], capture_output=True, text=True,
                              timeout=600)
    except subprocess.TimeoutExpired:
        return "error: update timed out after 10 minutes"
    out = (proc.stdout + proc.stderr).strip()
    return out if proc.returncode == 0 else f"FAILED (exit {proc.returncode}):\n{out}"


@mcp.tool()
def collection_status() -> str:
    """Summary of the exported MTGA collection: unique cards, total copies,
    rarity breakdown. Re-reads the export file if it changed."""
    owned = _collection()
    if not owned:
        return "no collection export found (run mtg-fetch collect first)"
    rarities: dict[str, int] = {}
    with db() as conn:
        for name, count in owned.items():
            row = conn.execute(
                "SELECT rarity FROM cards WHERE name = ? LIMIT 1", (name,)
            ).fetchone()
            r = row["rarity"] if row else "?"
            rarities[r] = rarities.get(r, 0) + count
    return "\n".join([
        f"unique names: {len(owned)}",
        f"total copies: {sum(owned.values())}",
        "by rarity: " + " ".join(f"{r}={n}" for r, n in sorted(rarities.items())),
    ])


@mcp.tool()
def owned(names: list[str]) -> str:
    """Batch: ownership check against the exported collection.
    Output: one line per card, 'N/4 Name' (owned; 4 is the nominal playset cap) or 'not owned Name'."""
    coll = _collection()
    lines = []
    with db() as conn:
        for name in names:
            resolved = _resolve_name(conn, name)
            n = coll.get(resolved or name, 0)
            if n:
                lines.append(f"{n}/4 {resolved or name}")
            else:
                lines.append(f"not owned {resolved or name}"
                             + ("" if resolved else " (unknown card)"))
    return "\n".join(lines)


@mcp.tool()
def collection_search(
    name_contains: str | None = None,
    text_regex: str | None = None,
    colors: str | None = None,
    identity: str | None = None,
    types: str | None = None,
    keyword: str | None = None,
    type_contains: str | None = None,
    rarity: str | None = None,
    max_mana_value: float | None = None,
    min_count: int = 1,
    limit: int = 50,
) -> str:
    """Search only cards you own (exported collection). Same filters as
    search_cards (colors, identity, types, keyword, ...) but restricted to
    owned cards and showing owned counts.
    Output: one line per card: 'Nx Name {cost} type :: text'"""
    coll = _collection()
    if not coll:
        return "no collection export found (run mtg-fetch collect first)"
    where, args = _search_filters(name_contains, text_regex, colors, identity,
                                  types, keyword, type_contains, rarity,
                                  max_mana_value)
    names_q = ",".join("?" for _ in coll)
    sql = f"""SELECT c.name, c.manaCost, c.type, c.text
              FROM cards c
              WHERE {' AND '.join(where)} AND c.name IN ({names_q})
              GROUP BY c.name ORDER BY c.name LIMIT 500"""

    with db() as conn:
        conn.create_function("regexp", 2, _regexp)
        rows = conn.execute(sql, args + list(coll)).fetchall()
    lines = [
        f'{coll[r["name"]]}x {r["name"]} {r["manaCost"] or ""} {r["type"]} :: {r["text"] or ""}'
        for r in rows if coll[r["name"]] >= min_count
    ][:limit]
    return "\n".join(lines) if lines else "no owned cards match"


def parse_decklist(decklist: str) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    main, side, in_side = [], [], False
    for line in decklist.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        low = line.lower()
        if low in ("deck", "main", "maindeck"):
            in_side = False
            continue
        if low in ("sideboard", "side"):
            in_side = True
            continue
        m = re.match(r"^(\d+)x?\s+(.+?)(?:\s+\(([A-Za-z0-9]+)\).*)?$", line)
        if not m:
            continue
        (side if in_side else main).append((int(m.group(1)), m.group(2).strip()))
    return main, side


@mcp.tool()
def deck_check(decklist: str, format: str = "standard") -> str:
    """Analyze an Arena-style decklist ('4 Card Name (SET) 123' lines, optional
    'Deck'/'Sideboard' headers). Names resolved fuzzily. Output sections:
      counts: maindeck N, sideboard N, unique N (maindeck count excludes unresolved cards)
      unknown: comma list (or 'none')
      illegal(<format>): comma list (or 'none')
      missing: cards to craft, qty needed (from exported collection, if present)
      wildcards: mythic=.. rare=.. uncommon=.. common=.. needed to craft missing
      curve: mv=count pairs, ascending
      pips: U=3 B=8 ... (weighted by qty)
      rarity: common=.. uncommon=.. rare=.. mythic=.."""
    main, side = parse_decklist(decklist)
    col = format.lower()
    coll = _collection()

    curve, pips, rarities = {}, {}, {}
    unknown, illegal, missing = [], [], []
    wildcards: dict[str, int] = {}
    resolved_map: dict[str, str] = {}
    total = 0
    with db() as conn:
        for orig in sorted({n for _, n in main + side}):
            name = _resolve_name(conn, orig)
            if not name:
                unknown.append(orig)
                continue
            resolved_map[orig] = name
            row = conn.execute(
                f"""SELECT c.name, c.manaCost, c.rarity, l.{col} AS ok
                    FROM cards c LEFT JOIN cardLegalities l ON c.uuid = l.uuid
                    LEFT JOIN sets s ON c.setCode = s.code
                    WHERE c.name = ? AND (c.side IS NULL OR c.side = 'a')
                    ORDER BY (s.type IN ('core', 'expansion')) DESC,
                             c.originalReleaseDate DESC""",
                (name,),
            ).fetchall()
            if not row:
                unknown.append(orig)
                continue
            if not any(r["ok"] == "Legal" for r in row):
                illegal.append(name)
            info = row[0]
            mana, rare = info["manaCost"], info["rarity"]
            qty_all = sum(q for q, n in main + side if n == orig)
            have = coll.get(name, 0)
            need = max(0, qty_all - have)
            if need and name not in ("Plains", "Island", "Swamp", "Mountain",
                                     "Forest", "Wastes"):
                missing.append(f"{need} {name} (have {have})")
                wildcards[rare] = wildcards.get(rare, 0) + need
            qty_main = sum(q for q, n in main if n == orig)
            if qty_main:
                total += qty_main

                def _mv(sym: str) -> int:
                    # handles hybrid/phyrexian: {2/W} -> 2, {W/U}, {G/P} -> 1
                    head = sym.split("/")[0]
                    if head.isdigit():
                        return int(head)
                    return 0 if head in "XYZ" else 1

                mv = sum(_mv(x) for x in re.findall(r"\{([^}]*)\}", mana or ""))
                curve[mv] = curve.get(mv, 0) + qty_main
                for p in re.findall(r"\{([WUBRG])(?:/[WUBRGP])?\}", mana or ""):
                    pips[p] = pips.get(p, 0) + qty_main
                rarities[rare] = rarities.get(rare, 0) + qty_main

    wc_order = ["mythic", "rare", "uncommon", "common"]
    return "\n".join([
        f"counts: maindeck {total}, sideboard {sum(q for q, _ in side)}, unique {len(resolved_map) + len(unknown)}",
        f"unknown: {', '.join(unknown) if unknown else 'none'}",
        f"illegal({col}): {', '.join(illegal) if illegal else 'none'}",
        "missing: " + (", ".join(missing) if missing else "none — you own it all"),
        "wildcards: " + (" ".join(f"{r}={wildcards[r]}" for r in wc_order if r in wildcards) or "none"),
        "curve: " + " ".join(f"{mv}={n}" for mv, n in sorted(curve.items())),
        "pips: " + " ".join(f"{p}={n}" for p, n in sorted(pips.items())),
        "rarity: " + " ".join(f"{r}={n}" for r, n in sorted(rarities.items())),
    ])


RHYSTIC_DB = "/home/bunny/.config/rhystic-tracker/rhystic.db"

_ALIVE = "m.id NOT IN (SELECT match_id FROM deleted_matches)"


def rhystic():
    conn = sqlite3.connect(f"file:{RHYSTIC_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return contextlib.closing(conn)


def _card_names(conn, grp_ids: set[int]) -> dict[int, str]:
    grp_ids = {g for g in grp_ids if g}
    if not grp_ids:
        return {}
    q = ",".join("?" for _ in grp_ids)
    rows = conn.execute(
        f"SELECT grp_id, name FROM cards_cache WHERE grp_id IN ({q})",
        list(grp_ids),
    ).fetchall()
    return {r["grp_id"]: r["name"] for r in rows}


def _card_name(names: dict[int, str], grp_id) -> str:
    if not grp_id:
        return "?"
    return names.get(grp_id, f"#{grp_id}")


def _result_mark(result: str) -> str:
    return {"win": "W", "loss": "L"}.get(result, "?")


def _fmt_duration(seconds) -> str:
    if seconds is None:
        return "?"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


@mcp.tool()
def list_games(limit: int = 20, deck: str | None = None,
               format: str | None = None, result: str | None = None) -> str:
    """Recent tracked matches from the Rhystic Tracker db, one line each:
      date  deck  format  W/L/?  vs opponent  turns
    Optional filters: deck (substring match on hero deck name), format (exact),
    result ('win' or 'loss'). Deleted matches excluded."""
    where, args = [_ALIVE], []
    if deck:
        where.append("m.hero_deck_name LIKE ?")
        args.append(f"%{deck}%")
    if format:
        where.append("m.format = ?")
        args.append(format)
    if result:
        where.append("m.result = ?")
        args.append(result)
    args.append(int(limit))
    sql = f"""SELECT m.* FROM matches m WHERE {' AND '.join(where)}
              ORDER BY m.timestamp DESC LIMIT ?"""
    with rhystic() as conn:
        rows = conn.execute(sql, args).fetchall()
    lines = [
        f'{r["date_str"]}  {r["hero_deck_name"]}  [{r["format"]}]  '
        f'{_result_mark(r["result"])}  vs {r["opponent_name"]}  '
        f'{r["turns"] or "?"} turns  ({r["id"]})'
        for r in rows
    ]
    return "\n".join(lines) if lines else "no matches found"


@mcp.tool()
def game_details(match_id: str | None = None) -> str:
    """Full detail of one match. match_id None = most recent non-deleted match.
    Sections: header (all match fields, commander ids resolved to names),
    hero cards seen, opponent cards seen, impactful cards, turn-by-turn event
    digest (grp_ids resolved; grouped per turn; very long logs truncated)."""
    with rhystic() as conn:
        if match_id:
            m = conn.execute(
                f"SELECT m.* FROM matches m WHERE m.id = ? AND {_ALIVE}",
                (match_id,),
            ).fetchone()
        else:
            m = conn.execute(
                f"SELECT m.* FROM matches m WHERE {_ALIVE} "
                "ORDER BY m.timestamp DESC LIMIT 1"
            ).fetchone()
        if not m:
            return "match not found"
        mid = m["id"]

        cards = conn.execute(
            "SELECT grp_id, is_opponent, count FROM match_cards WHERE match_id = ?",
            (mid,),
        ).fetchall()
        impacts = conn.execute(
            "SELECT * FROM match_impactful_cards WHERE match_id = ?",
            (mid,),
        ).fetchall()
        events = conn.execute(
            "SELECT turn_number, seat_id, event_type, grp_id "
            "FROM match_turn_events WHERE match_id = ? "
            "ORDER BY turn_number, id",
            (mid,),
        ).fetchall()

        grp_ids = {m["hero_commander_id"], m["opponent_commander_id"]}
        grp_ids |= {c["grp_id"] for c in cards}
        grp_ids |= {i["grp_id"] for i in impacts}
        grp_ids |= {e["grp_id"] for e in events}
        names = _card_names(conn, grp_ids)

    out = [
        f"match {mid}",
        f'date: {m["date_str"]} ({m["timestamp"]})  format: {m["format"]}  '
        f'result: {m["result"]} ({m["result_reason"] or "?"})',
        f'duration: {_fmt_duration(m["duration_seconds"])}  turns: {m["turns"]}  '
        f'going first: {"yes" if m["going_first"] else "no"}',
        f'hero: deck "{m["hero_deck_name"]}"  commander '
        f'{_card_name(names, m["hero_commander_id"])}  seat {m["hero_seat_id"]}  '
        f'life {m["hero_life_end"]}  mulligans {m["hero_mulligans"]}  '
        f'platform {m["hero_platform"] or "?"}',
        f'opponent: {m["opponent_name"]}  commander '
        f'{_card_name(names, m["opponent_commander_id"])}  '
        f'life {m["opponent_life_end"]}  mulligans {m["opponent_mulligans"]}  '
        f'platform {m["opponent_platform"] or "?"}',
    ]

    for opp in (False, True):
        seen = [c for c in cards if bool(c["is_opponent"]) == opp]
        seen.sort(key=lambda c: -c["count"])
        out.append(f'\n{"opponent" if opp else "hero"} cards seen ({len(seen)}):')
        out.extend(f'  {c["count"]}x {_card_name(names, c["grp_id"])}' for c in seen)

    if impacts:
        out.append("\nimpactful cards:")
        for i in impacts:
            bits = [
                f'total dmg {i["total_damage"]}' if i["total_damage"] else None,
                f'max hit {i["max_hit"]}' if i["max_hit"] else None,
                f'drew {i["cards_drawn"]}' if i["cards_drawn"] else None,
            ]
            titles = json.loads(i["titles"] or "[]")
            if titles:
                bits.append("titles: " + ", ".join(titles))
            who = "hero" if i["seat_id"] == m["hero_seat_id"] else "opp"
            out.append(f'  {_card_name(names, i["grp_id"])} ({who}): '
                       + "; ".join(b for b in bits if b))

    if events:
        out.append("\nturns:")
        by_turn: dict[int, list[str]] = {}
        for e in events:
            grp = _card_name(names, e["grp_id"])
            ev = e["event_type"]
            if ":" in ev and not ev.startswith(("destroy:", "sacrifice:", "bounce:")):
                txt = ev
            elif ev.startswith(("destroy:", "sacrifice:", "bounce:")):
                verb, _, target = ev.partition(":")
                txt = f'{verb} {grp}'
                if target and target.isdigit() and int(target) != e["grp_id"]:
                    txt += f' -> {_card_name(names, int(target))}'
            else:
                txt = f"{ev} {grp}"
            by_turn.setdefault(e["turn_number"], []).append(txt)
        shown, truncated = 0, 0
        max_lines = 80
        for turn in sorted(by_turn):
            evs = by_turn[turn]
            if shown + 1 > max_lines:
                truncated += 1
                continue
            if len(evs) > 12:
                shown_evs, hidden = evs[:12], len(evs) - 12
            else:
                shown_evs, hidden = evs, 0
            line = f'  t{turn}: ' + "; ".join(shown_evs)
            if hidden:
                line += f"; ... +{hidden} more"
            out.append(line)
            shown += 1
        if truncated:
            out.append(f"  ... {truncated} more turns truncated")
    return "\n".join(out)


@mcp.tool()
def last_game() -> str:
    """Full detail of the most recent non-deleted tracked match.
    Shortcut for game_details() with no match_id."""
    return game_details(None)


@mcp.tool()
def deck_history(deck_name: str) -> str:
    """Stats for a tracked deck by name (substring match): W/L, winrate,
    avg turns and duration, recent matches, and per-card performance
    aggregated from match_impactful_cards (total damage, max hit, cards drawn)."""
    with rhystic() as conn:
        rows = conn.execute(
            f"SELECT m.* FROM matches m WHERE {_ALIVE} "
            "AND m.hero_deck_name LIKE ? ORDER BY m.timestamp DESC",
            (f"%{deck_name}%",),
        ).fetchall()
        if not rows:
            return f"no matches found for deck like '{deck_name}'"
        ids = [r["id"] for r in rows]
        q = ",".join("?" for _ in ids)
        impacts = conn.execute(
            f"SELECT grp_id, total_damage, max_hit, cards_drawn "
            f"FROM match_impactful_cards WHERE match_id IN ({q})",
            ids,
        ).fetchall()
        names = _card_names(conn, {i["grp_id"] for i in impacts})

    wins = sum(1 for r in rows if r["result"] == "win")
    losses = sum(1 for r in rows if r["result"] == "loss")
    decided = wins + losses
    turns = [r["turns"] for r in rows if r["turns"]]
    durs = [r["duration_seconds"] for r in rows if r["duration_seconds"] is not None]

    out = [
        f'deck: {rows[0]["hero_deck_name"]}  ({len(rows)} matches'
        + (f", other names: {', '.join(sorted({r['hero_deck_name'] for r in rows if r['hero_deck_name'] != rows[0]['hero_deck_name']}))}"
           if len({r["hero_deck_name"] for r in rows}) > 1 else "") + ")",
        f"record: {wins}W {losses}L"
        + (f"  winrate {wins / decided:.0%}" if decided else ""),
        f"avg turns: {sum(turns) / len(turns):.1f}" if turns else "avg turns: ?",
        f"avg duration: {sum(durs) / len(durs) / 60:.1f} min" if durs else "",
        "",
        "recent matches:",
    ]
    out.extend(
        f'  {r["date_str"]}  {_result_mark(r["result"])}  vs {r["opponent_name"]}  '
        f'{r["turns"] or "?"} turns  [{r["format"]}]'
        for r in rows[:10]
    )

    agg: dict[str, dict[str, int]] = {}
    for i in impacts:
        a = agg.setdefault(_card_name(names, i["grp_id"]),
                           {"games": 0, "dmg": 0, "max": 0, "drew": 0})
        a["games"] += 1
        a["dmg"] += i["total_damage"] or 0
        a["max"] = max(a["max"], i["max_hit"] or 0)
        a["drew"] += i["cards_drawn"] or 0
    if agg:
        out.extend(["", "card performance (impactful cards):"])
        for name, a in sorted(agg.items(), key=lambda kv: -kv[1]["dmg"])[:15]:
            out.append(f'  {name}: {a["games"]} games, '
                       f'{a["dmg"]} total dmg, max hit {a["max"]}, drew {a["drew"]}')
    return "\n".join(x for x in out if x != "")


@mcp.tool()
def list_tracked_decks() -> str:
    """All decks stored in the tracker: card count, commander name, source,
    plus W/L record from tracked matches. One line per deck."""
    with rhystic() as conn:
        decks = conn.execute(
            "SELECT * FROM deck_lists ORDER BY updated_at DESC"
        ).fetchall()
        records = conn.execute(
            f"SELECT m.hero_deck_name, "
            f"SUM(m.result = 'win') AS w, SUM(m.result = 'loss') AS l "
            f"FROM matches m WHERE {_ALIVE} GROUP BY m.hero_deck_name"
        ).fetchall()
        names = _card_names(conn, {d["commander_grp_id"] for d in decks})
    rec = {r["hero_deck_name"]: (r["w"] or 0, r["l"] or 0) for r in records}
    lines = []
    for d in decks:
        cards = json.loads(d["cards_json"] or "[]")
        total = sum(c.get("count", 0) for c in cards)
        w, l = rec.get(d["deck_name"], (0, 0))
        lines.append(
            f'{d["deck_name"]}: {total} cards, commander '
            f'{_card_name(names, d["commander_grp_id"])}, {w}W {l}L'
            f'  (source {d["source"] or "?"}, updated {d["updated_at"] or "?"})'
        )
    return "\n".join(lines) if lines else "no decks stored"


@mcp.tool()
def deck_list(deck_name: str) -> str:
    """Stored decklist as MTGA text ('4 Card Name' lines), maindeck then
    'Sideboard' section. deck_name matched exactly, then as substring."""
    with rhystic() as conn:
        d = conn.execute(
            "SELECT * FROM deck_lists WHERE deck_name = ?", (deck_name,)
        ).fetchone()
        if not d:
            d = conn.execute(
                "SELECT * FROM deck_lists WHERE deck_name LIKE ?",
                (f"%{deck_name}%",),
            ).fetchone()
        if not d:
            return f"no stored deck like '{deck_name}'"
        main = json.loads(d["cards_json"] or "[]")
        side = json.loads(d["sideboard_json"] or "[]")
        grp_ids = {c.get("grp_id") for c in main + side}
        if d["commander_grp_id"]:
            grp_ids.add(d["commander_grp_id"])
        names = _card_names(conn, grp_ids)
    lines = [f"# {d['deck_name']}", "Deck"]
    lines.extend(f'{c.get("count", 1)} {_card_name(names, c.get("grp_id"))}' for c in main)
    if side:
        lines.append("Sideboard")
        lines.extend(f'{c.get("count", 1)} {_card_name(names, c.get("grp_id"))}' for c in side)
    return "\n".join(lines)


if __name__ == "__main__":
    mcp.run()
