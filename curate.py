#!/usr/bin/env python3
"""
Write curation verdicts to the database.

Claude calls this after applying the filter taxonomy to a window. It
records, per item, whether the item is included in the digest and which
section it belongs to, so re-runs over an overlapping window reuse prior
judgments instead of re-deciding.

Verdicts JSON shape (read from --verdicts FILE or stdin):

{
  "260411p5":  {"verdict": "include", "section": "AI model & product releases"},
  "260411p7":  {"verdict": "skip"}
}

Usage:
    curate.py list-unjudged --start 2026-04-12 --end 2026-04-18
    curate.py write --verdicts /tmp/verdicts.json
    curate.py clear --start 2026-04-12 --end 2026-04-18
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

import db


def _resolve_window(args) -> tuple[str, str] | None:
    """Resolve --this-week / --last-week into (start, end) date strings."""
    if getattr(args, "this_week", False):
        s, e = db.week_bounds("this-week")
        return s.isoformat(), e.isoformat()
    if getattr(args, "last_week", False):
        s, e = db.week_bounds("last-week")
        return s.isoformat(), e.isoformat()
    if args.start and not args.end:
        print("ERROR: --start requires --end", file=sys.stderr)
        return None
    return args.start, args.end


def cmd_list_unjudged(args) -> int:
    result = _resolve_window(args)
    if result is None:
        return 2
    start, end = result
    conn = db.connect()
    rows = db.items_in_window(conn, start, end)
    unjudged = [r for r in rows if r["verdict"] is None]
    out = [
        {"id": r["id"], "item_date": r["item_date"], "headline": r["headline"], "source": r["source"]}
        for r in unjudged
    ]
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    print(f"# {len(unjudged)} unjudged of {len(rows)} items in window {start}..{end}", file=sys.stderr)
    return 0


def cmd_write(args) -> int:
    payload = json.loads(Path(args.verdicts).read_text()) if args.verdicts else json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        print("ERROR: verdicts must be a JSON object keyed by item id", file=sys.stderr)
        return 2

    now = dt.datetime.now().isoformat(timespec="seconds")
    conn = db.connect()
    written = skipped = 0
    for item_id, v in payload.items():
        verdict = v.get("verdict")
        if verdict not in ("include", "skip"):
            print(f"WARNING: bad verdict for {item_id}: {verdict!r}", file=sys.stderr)
            skipped += 1
            continue
        section = v.get("section") if verdict == "include" else None
        if verdict == "include" and not section:
            print(f"WARNING: include verdict for {item_id} missing section", file=sys.stderr)
            skipped += 1
            continue
        conn.execute(
            """INSERT INTO curation (item_id, verdict, section, decided_at)
                 VALUES (?, ?, ?, ?)
                 ON CONFLICT(item_id) DO UPDATE SET
                   verdict=excluded.verdict, section=excluded.section, decided_at=excluded.decided_at""",
            (item_id, verdict, section, now),
        )
        written += 1
    conn.commit()
    print(f"wrote {written} verdicts, skipped {skipped}")
    return 0


def cmd_clear(args) -> int:
    result = _resolve_window(args)
    if result is None:
        return 2
    start, end = result
    conn = db.connect()
    n = conn.execute(
        """DELETE FROM curation WHERE item_id IN (
              SELECT id FROM items WHERE item_date BETWEEN ? AND ?)""",
        (start, end),
    ).rowcount
    conn.commit()
    print(f"cleared {n} verdicts in window {start}..{end}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    lu = sub.add_parser("list-unjudged", help="print items in window with no prior verdict")
    lu_win = lu.add_mutually_exclusive_group(required=True)
    lu_win.add_argument("--this-week", action="store_true", help="Sunday through today")
    lu_win.add_argument("--last-week", action="store_true", help="previous completed Sun–Sat")
    lu_win.add_argument("--start", help="YYYY-MM-DD (requires --end)")
    lu.add_argument("--end", help="YYYY-MM-DD (required with --start)")
    lu.set_defaults(fn=cmd_list_unjudged)

    wr = sub.add_parser("write", help="write verdicts from JSON (stdin or --verdicts)")
    wr.add_argument("--verdicts", help="path to verdicts JSON (default: stdin)")
    wr.set_defaults(fn=cmd_write)

    cl = sub.add_parser("clear", help="delete verdicts for items in a window")
    cl_win = cl.add_mutually_exclusive_group(required=True)
    cl_win.add_argument("--this-week", action="store_true", help="Sunday through today")
    cl_win.add_argument("--last-week", action="store_true", help="previous completed Sun–Sat")
    cl_win.add_argument("--start", help="YYYY-MM-DD (requires --end)")
    cl.add_argument("--end", help="YYYY-MM-DD (required with --start)")
    cl.set_defaults(fn=cmd_clear)

    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
