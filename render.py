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


def _week_saturday(start: dt.date) -> dt.date:
    """Return the Saturday ending the Sun→Sat week containing `start`."""
    if start.weekday() == 6:  # Sunday
        return start + dt.timedelta(days=6)
    return start + dt.timedelta(days=(5 - start.weekday()) % 7)


def _week_title(start: dt.date, end: dt.date) -> str:
    """Always shows the full Sun–Sat week: 'Week of Apr 12 – Apr 18, 2026'."""
    sat = _week_saturday(start)
    if start.year == sat.year:
        return f"Week of {start.strftime('%b %-d')} \u2013 {sat.strftime('%b %-d, %Y')}"
    return f"Week of {start.strftime('%b %-d, %Y')} \u2013 {sat.strftime('%b %-d, %Y')}"


def _week_subtitle(start: dt.date, end: dt.date, partial: bool) -> str:
    """Shows the actual data range: 'Sun 2026-04-12 → Tue 2026-04-15 (partial)'."""
    s = f"{start.strftime('%a')} {start.isoformat()} \u2192 {end.strftime('%a')} {end.isoformat()}"
    if partial:
        s += " (partial)"
    return s


def _is_partial(start: dt.date, end: dt.date) -> bool:
    """A week is partial if end doesn't reach the Saturday of start's week."""
    return end < _week_saturday(start)


def write_index() -> None:
    """Regenerate digests/index.html from the current set of digest files."""
    digests_dir = REPO / "digests"
    files = sorted(digests_dir.glob("*_week.html"), reverse=True)

    items = []
    for f in files:
        stem = f.stem  # e.g. "2026-04-19_week"
        date_part = stem.replace("_week", "")
        try:
            start = dt.date.fromisoformat(date_part)
        except ValueError:
            continue
        items.append({"href": f.name, "title": _week_title(start, _week_saturday(start))})

    html = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Big Tech News</title>
<style>
  :root {
    --bg: #fafaf7; --fg: #1c1c1c; --muted: #6b6b6b;
    --rule: #e6e3da; --link: #1c1c1c; --link-hover: #b3261e;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #161614; --fg: #ececec; --muted: #999;
      --rule: #2a2a27; --link: #ececec; --link-hover: #ff8a80;
    }
  }
  html, body { background: var(--bg); color: var(--fg);
    font-family: -apple-system, BlinkMacSystemFont, "Helvetica Neue", system-ui, sans-serif;
    line-height: 1.45; margin: 0; }
  main { max-width: 720px; margin: 0 auto; padding: 3rem 1.25rem 5rem; }
  header { border-bottom: 1px solid var(--rule); padding-bottom: 1.25rem; margin-bottom: 1.5rem; }
  h1 { font-size: 1.75rem; margin: 0; letter-spacing: -0.01em; }
  ul { list-style: none; padding: 0; margin: 0; }
  li { padding: .55rem 0; border-bottom: 1px dotted var(--rule); }
  li:last-child { border-bottom: none; }
  a { color: var(--link); text-decoration: none; font-weight: 500; }
  a:hover { color: var(--link-hover); text-decoration: underline; }
</style>
</head>
<body>
<main>
<header><h1>Big Tech News</h1></header>
<ul>
"""
    for item in items:
        html += f'  <li><a href="{item["href"]}">{item["title"]}</a></li>\n'
    html += "</ul>\n</main>\n</body>\n</html>\n"

    out = digests_dir / "index.html"
    out.write_text(html, encoding="utf-8")


def _auto_out_path(start: dt.date, end: dt.date, partial: bool) -> Path:
    """Compute output path following CLAUDE.md filename conventions."""
    delta = (end - start).days
    if delta <= 6:
        suffix = "_week.html"
        return Path(f"digests/{start.isoformat()}{suffix}")
    return Path(f"digests/{start.isoformat()}_to_{end.isoformat()}.html")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", help="output HTML path (auto-computed from window if omitted)")
    p.add_argument("--title", help="override auto-computed title")
    p.add_argument("--subtitle", help="override auto-computed subtitle")
    p.add_argument("--partial", action="store_true", default=None,
                   help="override partial detection (auto-detected from window if omitted)")

    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--this-week", action="store_true", help="Sunday through today (partial)")
    mode.add_argument("--last-week", action="store_true", help="previous completed Sun–Sat")
    mode.add_argument("--window", help="START..END (YYYY-MM-DD..YYYY-MM-DD)")
    mode.add_argument("--spec", help="path to spec JSON (legacy manual mode)")
    mode.add_argument("--spec-stdin", action="store_true", help="read spec JSON from stdin")

    args = p.parse_args()
    conn = db.connect()

    if args.this_week or args.last_week:
        which = "this-week" if args.this_week else "last-week"
        start, end = db.week_bounds(which)
        start_s, end_s = start.isoformat(), end.isoformat()
    elif args.window:
        try:
            start_s, end_s = args.window.split("..")
            start = dt.date.fromisoformat(start_s)
            end = dt.date.fromisoformat(end_s)
        except ValueError:
            print("ERROR: --window must be START..END (YYYY-MM-DD..YYYY-MM-DD)", file=sys.stderr)
            return 2

    if args.this_week or args.last_week or args.window:
        sections = build_sections_from_window(conn, start_s, end_s)
        partial = args.partial if args.partial is not None else _is_partial(start, end)
        title = args.title or _week_title(start, end)
        subtitle = args.subtitle or _week_subtitle(start, end, partial)
        out_path = Path(args.out) if args.out else _auto_out_path(start, end, partial)
    else:
        if not args.out:
            print("ERROR: --out is required with --spec/--spec-stdin", file=sys.stderr)
            return 2
        spec = json.loads(Path(args.spec).read_text()) if args.spec else json.loads(sys.stdin.read())
        sections = build_sections_from_spec(conn, spec)
        title = args.title or spec.get("title", "Big Tech News Digest")
        subtitle = args.subtitle or spec.get("subtitle", "")
        partial = args.partial or spec.get("partial", False)
        dates = sorted({it["item_date"] for s in sections for it in s["entries"]})
        start_s, end_s = (dates[0], dates[-1]) if dates else (dt.date.today().isoformat(),) * 2
        out_path = Path(args.out)

    days = build_days(start_s, end_s, sections)
    render(sections, days, title=title, subtitle=subtitle, partial=partial, out_path=out_path)
    write_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
