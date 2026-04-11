#!/usr/bin/env python3
"""
Daily Techmeme fetcher.

Fetches one or more Techmeme archive pages and stores every story item
into a local sqlite database. Idempotent: re-running on the same day
upserts existing rows so it's safe to call repeatedly.

Usage:
    fetch.py                       # fetch today
    fetch.py --days 14             # fetch the last 14 days (backfill)
    fetch.py --date 2026-04-09     # fetch a specific date
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

REPO = Path(__file__).resolve().parent
DB_PATH = REPO / "archive.db"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Safari/605.1.15"
)
ITEM_ID_RE = re.compile(r"^(\d{6})p(\d+)$")


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
            id            TEXT PRIMARY KEY,   -- e.g. "260409p22"
            item_date     TEXT NOT NULL,      -- YYYY-MM-DD (derived from id)
            permalink     TEXT NOT NULL,      -- techmeme cluster permalink
            headline      TEXT NOT NULL,
            source        TEXT,               -- "Author / Publication"
            is_lead       INTEGER NOT NULL,   -- 1 = lead of cluster / standalone
            cluster_index INTEGER,            -- ordinal of containing cluster, NULL if standalone
            first_seen    TEXT NOT NULL,      -- ISO timestamp of first capture
            last_seen     TEXT NOT NULL       -- ISO timestamp of most recent capture
        );
        CREATE INDEX IF NOT EXISTS idx_items_date ON items(item_date);
        CREATE INDEX IF NOT EXISTS idx_items_lead ON items(is_lead);
        """
    )
    return conn


def yyMMdd(d: dt.date) -> str:
    return d.strftime("%y%m%d")


def iso_date_from_id(item_id: str) -> str:
    m = ITEM_ID_RE.match(item_id)
    if not m:
        raise ValueError(f"bad item id: {item_id}")
    yymmdd = m.group(1)
    yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    return dt.date(2000 + yy, mm, dd).isoformat()


def fetch_archive(date: dt.date) -> str:
    """Fetch a Techmeme dated archive page. Uses /YYMMDD/p1 (the trailing
    slash form returns 403). Raises on non-200."""
    url = f"https://www.techmeme.com/{yyMMdd(date)}/p1"
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.text


def parse_items(html: str) -> list[dict]:
    """Parse a Techmeme archive page and return a list of item dicts.

    Each item: {id, permalink, headline, source, is_lead, cluster_index}
    Items in a div.clus are members of a cluster; the first is the lead.
    Items outside a div.clus are treated as standalone leads (cluster_index=None).
    """
    soup = BeautifulSoup(html, "html.parser")
    items: list[dict] = []
    seen: set[str] = set()

    # First, walk div.clus blocks in order to capture cluster membership.
    for cluster_index, clus in enumerate(soup.select("div.clus")):
        inner = clus.select("div.itc2[id]")
        for pos, itc2 in enumerate(inner):
            item_id = itc2.get("id", "")
            if not ITEM_ID_RE.match(item_id) or item_id in seen:
                continue
            seen.add(item_id)
            d = _build_item(itc2, item_id, is_lead=(pos == 0), cluster_index=cluster_index)
            if d:
                items.append(d)

    # Then, capture any itc2[id] still unseen (sections outside div.clus).
    for itc2 in soup.find_all("div", id=ITEM_ID_RE):
        item_id = itc2.get("id", "")
        if item_id in seen:
            continue
        seen.add(item_id)
        d = _build_item(itc2, item_id, is_lead=True, cluster_index=None)
        if d:
            items.append(d)

    return items


def _build_item(itc2, item_id: str, *, is_lead: bool, cluster_index: int | None) -> dict | None:
    # headline anchor
    a = itc2.select_one("a.ourh") or itc2.select_one("strong a")
    if not a:
        return None
    headline = a.get_text(" ", strip=True)
    if not headline:
        return None
    # source: <cite>Author / <a>Publication</a>:</cite>
    cite = itc2.find("cite")
    source = cite.get_text(" ", strip=True).rstrip(":") if cite else None
    yymmdd, pn = ITEM_ID_RE.match(item_id).groups()
    permalink = f"https://www.techmeme.com/{yymmdd}/p{pn}#a{item_id}"
    return {
        "id": item_id,
        "permalink": permalink,
        "headline": headline,
        "source": source,
        "is_lead": 1 if is_lead else 0,
        "cluster_index": cluster_index,
    }


def upsert(conn: sqlite3.Connection, items: list[dict]) -> tuple[int, int]:
    now = dt.datetime.now().isoformat(timespec="seconds")
    inserted = updated = 0
    cur = conn.cursor()
    for it in items:
        item_date = iso_date_from_id(it["id"])
        cur.execute("SELECT 1 FROM items WHERE id = ?", (it["id"],))
        exists = cur.fetchone() is not None
        if exists:
            cur.execute(
                """UPDATE items
                   SET headline=?, source=?, is_lead=?, cluster_index=?, last_seen=?
                   WHERE id=?""",
                (it["headline"], it["source"], it["is_lead"], it["cluster_index"], now, it["id"]),
            )
            updated += 1
        else:
            cur.execute(
                """INSERT INTO items
                   (id, item_date, permalink, headline, source, is_lead, cluster_index, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    it["id"], item_date, it["permalink"], it["headline"], it["source"],
                    it["is_lead"], it["cluster_index"], now, now,
                ),
            )
            inserted += 1
    conn.commit()
    return inserted, updated


def fetch_and_store(conn: sqlite3.Connection, date: dt.date) -> tuple[int, int, int]:
    html = fetch_archive(date)
    items = parse_items(html)
    ins, upd = upsert(conn, items)
    return len(items), ins, upd


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--days", type=int, default=1, help="number of days back to fetch (default: 1, i.e. today)")
    p.add_argument("--date", type=str, help="fetch a specific date YYYY-MM-DD (overrides --days)")
    p.add_argument("--sleep", type=float, default=1.0, help="seconds between requests when --days > 1")
    args = p.parse_args()

    conn = db_connect()
    today = dt.date.today()

    if args.date:
        targets = [dt.date.fromisoformat(args.date)]
    else:
        targets = [today - dt.timedelta(days=i) for i in range(args.days)]

    for i, d in enumerate(targets):
        try:
            total, ins, upd = fetch_and_store(conn, d)
            print(f"[{d.isoformat()}] parsed={total}  inserted={ins}  updated={upd}")
        except Exception as e:
            print(f"[{d.isoformat()}] ERROR: {e}", file=sys.stderr)
        if i < len(targets) - 1:
            time.sleep(args.sleep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
