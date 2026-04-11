#!/usr/bin/env python3
"""
Render a digest HTML file from a JSON spec.

The JSON spec describes the curation Claude (or you) decided on. It must
NOT contain prose summaries. Item ids are looked up in archive.db so the
final HTML always shows the verbatim Techmeme headline + verified permalink.

Spec format (read from stdin or --spec FILE):

{
  "title": "Week of Apr 5 – Apr 11, 2026",
  "subtitle": "Sun 2026-04-05 \u2192 Sat 2026-04-11",
  "partial": false,
  "sections": [
    {"name": "AI model releases", "item_ids": ["260408p42", "260409p3"]},
    {"name": "Platform & policy", "item_ids": ["260404p2"]}
  ]
}

Usage:
    cat spec.json | render.py --out digests/2026-04-05_week.html
    render.py --spec spec.json --out digests/2026-04-05_week.html
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

REPO = Path(__file__).resolve().parent
DB_PATH = REPO / "archive.db"
TEMPLATES = REPO / "templates"
DIGESTS = REPO / "digests"


def load_items(item_ids: list[str]) -> dict[str, dict]:
    if not item_ids:
        return {}
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(item_ids))
    rows = conn.execute(
        f"SELECT id, item_date, permalink, headline, source FROM items WHERE id IN ({placeholders})",
        item_ids,
    ).fetchall()
    return {
        r[0]: {"id": r[0], "item_date": r[1], "permalink": r[2], "headline": r[3], "source": r[4]}
        for r in rows
    }


def render(spec: dict, out_path: Path) -> None:
    all_ids = [iid for s in spec.get("sections", []) for iid in s.get("item_ids", [])]
    items = load_items(all_ids)

    missing = [iid for iid in all_ids if iid not in items]
    if missing:
        print(f"WARNING: {len(missing)} item id(s) not found in archive.db: {missing[:5]}{'...' if len(missing) > 5 else ''}", file=sys.stderr)

    sections = []
    for s in spec.get("sections", []):
        resolved = [items[iid] for iid in s.get("item_ids", []) if iid in items]
        if resolved:
            sections.append({"name": s["name"], "entries": resolved})

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
    )
    tpl = env.get_template("digest.html.j2")
    html = tpl.render(
        title=spec.get("title", "Big Tech News Digest"),
        subtitle=spec.get("subtitle", ""),
        partial=bool(spec.get("partial", False)),
        sections=sections,
        generated_at=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        total=sum(len(s["entries"]) for s in sections),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    print(f"wrote {out_path}  ({sum(len(s['entries']) for s in sections)} items, {len(sections)} sections)")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--spec", type=str, help="path to spec JSON (default: stdin)")
    p.add_argument("--out", type=str, required=True, help="output HTML path")
    args = p.parse_args()

    if args.spec:
        spec = json.loads(Path(args.spec).read_text())
    else:
        spec = json.loads(sys.stdin.read())

    render(spec, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
