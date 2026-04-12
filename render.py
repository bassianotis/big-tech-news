#!/usr/bin/env python3
"""
Render a digest HTML file.

Two modes:

1. --window START..END  (preferred; pairs with curate.py)
   Reads the curation table and assembles sections from items with
   verdict='include' in range. Adds a per-day filter to the HTML,
   one button per day in the window.

2. --spec FILE (or stdin)
   Legacy / manual mode: explicit JSON spec listing item ids per section.
   The day filter is still emitted, covering the dates actually present.

Either way, every headline and permalink comes verbatim from archive.db —
the renderer never trusts prose from its caller.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

import db

REPO = Path(__file__).resolve().parent
TEMPLATES = REPO / "templates"

# Canonical section order. Unknown sections fall to the end.
SECTION_ORDER = [
    "AI model & product releases",
    "Capability thresholds",
    "Revenue & scale milestones",
    "User behavior & adoption",
    "Platform & policy",
    "Infrastructure & compute",
    "Deals & funding",
    "Regulation & legal",
    "Geopolitics & trade",
    "Hardware & devices",
    "Research & ideas",
    "Voices & interviews",
    "Industry narratives",
    "Beyond AI",
]


def _section_sort_key(name: str) -> tuple[int, str]:
    try:
        return (SECTION_ORDER.index(name), name)
    except ValueError:
        return (len(SECTION_ORDER), name)


def _load_items_by_id(conn, ids: list[str]) -> dict[str, dict]:
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id, item_date, permalink, headline, source FROM items WHERE id IN ({placeholders})",
        ids,
    ).fetchall()
    return {
        r[0]: {"id": r[0], "item_date": r[1], "permalink": r[2], "headline": r[3], "source": r[4]}
        for r in rows
    }


def build_sections_from_window(conn, start: str, end: str) -> list[dict]:
    rows = db.items_in_window(conn, start, end)
    by_section: dict[str, list[dict]] = {}
    for r in rows:
        if r["verdict"] != "include":
            continue
        sec = r["section"] or "Uncategorized"
        by_section.setdefault(sec, []).append(
            {"id": r["id"], "item_date": r["item_date"], "permalink": r["permalink"],
             "headline": r["headline"], "source": r["source"]}
        )
    ordered = sorted(by_section.items(), key=lambda kv: _section_sort_key(kv[0]))
    return [{"name": name, "entries": entries} for name, entries in ordered]


def build_sections_from_spec(conn, spec: dict) -> list[dict]:
    all_ids = [iid for s in spec.get("sections", []) for iid in s.get("item_ids", [])]
    items = _load_items_by_id(conn, all_ids)
    missing = [iid for iid in all_ids if iid not in items]
    if missing:
        print(f"WARNING: {len(missing)} item id(s) not in archive.db: {missing[:5]}", file=sys.stderr)
    sections = []
    for s in spec.get("sections", []):
        resolved = [items[iid] for iid in s.get("item_ids", []) if iid in items]
        if resolved:
            sections.append({"name": s["name"], "entries": resolved})
    return sections


def build_days(start: str, end: str, sections: list[dict]) -> list[dict]:
    """One entry per date in [start, end], each with count of visible items on that date."""
    s = dt.date.fromisoformat(start)
    e = dt.date.fromisoformat(end)
    counts: dict[str, int] = {}
    for sec in sections:
        for item in sec["entries"]:
            counts[item["item_date"]] = counts.get(item["item_date"], 0) + 1
    days = []
    d = s
    while d <= e:
        iso = d.isoformat()
        days.append({
            "iso": iso,
            "label": d.strftime("%a %-m/%-d"),  # e.g. "Sun 4/5"
            "count": counts.get(iso, 0),
        })
        d += dt.timedelta(days=1)
    return days


def render(sections: list[dict], days: list[dict], *, title: str, subtitle: str, partial: bool, out_path: Path) -> None:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("digest.html.j2")
    html = tpl.render(
        title=title, subtitle=subtitle, partial=partial,
        sections=sections, days=days,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        total=sum(len(s["entries"]) for s in sections),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path}  ({sum(len(s['entries']) for s in sections)} items, {len(sections)} sections, {len(days)} days)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="output HTML path")
    p.add_argument("--title", help="digest title")
    p.add_argument("--subtitle", help="digest subtitle")
    p.add_argument("--partial", action="store_true", help="mark digest as partial")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--window", help="START..END (YYYY-MM-DD..YYYY-MM-DD)")
    mode.add_argument("--spec", help="path to spec JSON (legacy manual mode)")
    mode.add_argument("--spec-stdin", action="store_true", help="read spec JSON from stdin")

    args = p.parse_args()
    conn = db.connect()

    if args.window:
        try:
            start, end = args.window.split("..")
            dt.date.fromisoformat(start)
            dt.date.fromisoformat(end)
        except ValueError:
            print("ERROR: --window must be START..END (YYYY-MM-DD..YYYY-MM-DD)", file=sys.stderr)
            return 2
        sections = build_sections_from_window(conn, start, end)
        title = args.title or f"Digest {start} \u2192 {end}"
        subtitle = args.subtitle or f"{start} \u2192 {end}"
    else:
        spec = json.loads(Path(args.spec).read_text()) if args.spec else json.loads(sys.stdin.read())
        sections = build_sections_from_spec(conn, spec)
        title = args.title or spec.get("title", "Big Tech News Digest")
        subtitle = args.subtitle or spec.get("subtitle", "")
        if spec.get("partial"):
            args.partial = True
        dates = sorted({it["item_date"] for s in sections for it in s["entries"]})
        start, end = (dates[0], dates[-1]) if dates else (dt.date.today().isoformat(),) * 2

    days = build_days(start, end, sections)
    render(sections, days, title=title, subtitle=subtitle, partial=args.partial, out_path=Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
