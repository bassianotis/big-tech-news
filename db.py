"""
Shared sqlite helpers.

One source of truth for the schema so fetch.py, curate.py, and render.py
all agree. Tables are created with `IF NOT EXISTS` so this is safe to
run on an existing database.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parent
DB_PATH = REPO / "archive.db"

SCHEMA = """
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

CREATE TABLE IF NOT EXISTS curation (
    item_id     TEXT PRIMARY KEY,
    verdict     TEXT NOT NULL,        -- 'include' | 'skip'
    section     TEXT,                 -- section name if verdict='include'
    decided_at  TEXT NOT NULL,
    FOREIGN KEY (item_id) REFERENCES items(id)
);
CREATE INDEX IF NOT EXISTS idx_curation_verdict ON curation(verdict);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn


def items_in_window(conn: sqlite3.Connection, start: str, end: str, *, leads_only: bool = True) -> list[dict]:
    """Items in [start, end] inclusive, LEFT JOINed with prior verdicts."""
    sql = """
        SELECT i.id, i.item_date, i.permalink, i.headline, i.source, i.is_lead,
               c.verdict, c.section
          FROM items i
          LEFT JOIN curation c ON c.item_id = i.id
         WHERE i.item_date BETWEEN ? AND ?
    """
    if leads_only:
        sql += " AND i.is_lead = 1"
    sql += " ORDER BY i.item_date, i.id"
    return [
        {"id": r[0], "item_date": r[1], "permalink": r[2], "headline": r[3],
         "source": r[4], "is_lead": r[5], "verdict": r[6], "section": r[7]}
        for r in conn.execute(sql, (start, end)).fetchall()
    ]
