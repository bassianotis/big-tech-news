# big-tech-news

A personal Techmeme digest pipeline. Captures every story item from
Techmeme's daily archive into a local sqlite database, then lets you ask
[Claude Code](https://claude.com/claude-code) to curate a window (e.g.
last week, last month) into a clean HTML digest. The digest contains
nothing but verbatim Techmeme headlines and verified Techmeme cluster
permalinks — **no AI prose, no summaries**. Each link points to a
Techmeme cluster page, which aggregates every source for that story.

> **For personal use.** This tool fetches Techmeme's public archive
> pages and stores headlines locally for personal reading. It does not
> redistribute Techmeme content. Be respectful of
> [Techmeme's terms](https://www.techmeme.com/about) — don't run
> aggressive fetch schedules, and don't republish the captured archive.
> The default fetch (1 page/day) is well within reasonable use; the
> 14-day backfill is 14 sequential requests with a 1s sleep, which is
> also fine. Don't crank `--days` to absurd values.

> **Requires Claude Code.** The curation step assumes you have Claude
> Code installed and an active Anthropic subscription. The capture and
> render scripts are pure Python with no LLM dependency, so you can use
> just those independently if you want a different curation flow.

> **Best-effort scraper.** Techmeme's HTML structure is stable but not
> guaranteed. If they restructure, `fetch.py` may need a parser tweak.

## Why

The goal isn't "what happened today" — it's "what shifted that I should
know about". Daily news fatigue, fixed. The capture is automatic; you
read on whatever cadence makes sense for you.

## Layout

```
big-tech-news/
├── CLAUDE.md             # filter taxonomy + curation instructions for Claude Code
├── fetch.py              # daily Techmeme fetcher → sqlite (no LLM)
├── render.py             # JSON spec → HTML digest (no LLM)
├── archive.db            # sqlite store of every captured item
├── templates/
│   └── digest.html.j2    # HTML template
├── digests/              # generated digests (gitignored)
├── launchd/
│   └── com.example.bigtechnews.plist.template  # macOS daily fetch job (template)
├── LICENSE               # GPLv3
└── requirements.txt
```

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python fetch.py --days 14    # backfill the last 2 weeks
```

## Daily fetch (launchd, macOS)

The committed plist is a template with a `{{REPO}}` placeholder. To install:

```bash
# Pick your own reverse-DNS prefix (replace `com.yourname`).
REPO="$(pwd)"
sed "s|{{REPO}}|$REPO|g" launchd/com.example.bigtechnews.plist.template \
  > ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
# Edit the Label inside the file too if you changed the prefix.
launchctl load ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
```

Runs at 06:00 local time. Fetches the last 2 days (so a missed run gets
caught up the next morning). Re-runs are idempotent.

To disable:
```bash
launchctl unload ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
```

## Generating a digest

Open this repo in Claude Code and ask for a digest in plain English:

> *"Give me this week's digest."*
> *"Catch me up on the last 4 weeks."*
> *"Generate a digest for the week of March 22."*

Claude reads `CLAUDE.md`, queries the archive, applies the filter
taxonomy, builds a JSON spec, and pipes it to `render.py`. The output
lands in `digests/` as a self-contained HTML file. Open it in your
browser.

The LLM only **picks and categorizes** items — every headline and link
is loaded verbatim from the database by `render.py`, so the digest is
never paraphrased or hallucinated.

## Manual digest generation

You can also build a spec by hand and render it directly:

```bash
cat > /tmp/spec.json <<'JSON'
{
  "title": "Week of Apr 5 \u2013 Apr 11, 2026",
  "subtitle": "Sun 2026-04-05 \u2192 Sat 2026-04-11",
  "partial": false,
  "sections": [
    {"name": "AI model & product releases", "item_ids": ["260408p42"]},
    {"name": "Platform & policy",           "item_ids": ["260404p2"]}
  ]
}
JSON
.venv/bin/python render.py --spec /tmp/spec.json --out digests/2026-04-05_week.html
```

## Database schema

```sql
CREATE TABLE items (
  id            TEXT PRIMARY KEY,    -- e.g. "260409p22"
  item_date     TEXT NOT NULL,       -- YYYY-MM-DD (from id prefix)
  permalink     TEXT NOT NULL,       -- techmeme.com/YYMMDD/pNN#aYYMMDDpNN
  headline      TEXT NOT NULL,
  source        TEXT,                -- "Author / Publication"
  is_lead       INTEGER NOT NULL,    -- 1 = lead of cluster / standalone
  cluster_index INTEGER,             -- ordinal of cluster on page, NULL if standalone
  first_seen    TEXT NOT NULL,       -- ISO timestamp first captured
  last_seen     TEXT NOT NULL        -- ISO timestamp most recently captured
);
```

Lead items are the canonical "top of the cluster" stories. Curation
defaults to leads only — non-leads are usually secondary coverage and
would create duplicates.

## License

[GPLv3](LICENSE). Fork freely. The filter taxonomy in [CLAUDE.md](CLAUDE.md)
reflects one person's interests — edit it to match yours.

## Future: Pi migration

`fetch.py` is pure Python with no Mac-specific deps. To move capture to
a Raspberry Pi:

1. Drop the repo into a small Docker image (Python 3.11+ + requirements).
2. Run `fetch.py` daily via cron inside the container.
3. Sync `archive.db` back to your Mac (rsync, syncthing, or commit-to-git).
4. Curation continues to happen in Claude Code on the Mac.
