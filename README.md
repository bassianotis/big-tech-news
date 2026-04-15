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
├── curate.py             # verdict writer (include/skip per item)
├── render.py             # renders HTML digest from curation table (no LLM)
├── db.py                 # shared sqlite schema and helpers
├── templates/
│   └── digest.html.j2    # HTML template with day-of-week filter
├── docker/
│   ├── app/              # Dockerfile + entrypoint + crontab for app container
│   └── web/              # nginx config for static digest serving
├── docker-compose.yml    # two services: app (Python + Claude Code) + web (nginx)
├── data/                 # runtime data — gitignored contents, committed structure
│   ├── archive.db        # sqlite store of every captured item
│   ├── digests/          # generated HTML digests
│   └── launchd/          # fetch logs
├── config/
│   └── claude/           # Claude Code auth token — never committed
├── launchd/
│   └── com.example.bigtechnews.plist.template  # macOS daily fetch job (template)
├── LICENSE               # GPLv3
└── requirements.txt
```

## Deployment: Raspberry Pi (recommended)

The canonical setup runs on a Raspberry Pi (arm64) as two Docker
containers behind an existing nginx reverse proxy. Fetch runs
automatically; curation happens interactively over SSH when you want a
digest.

**Prerequisites:** Pi OS 64-bit (`uname -m` → `aarch64`), Docker,
nginx-proxy-manager (or equivalent reverse proxy).

```bash
# 1. Clone
git clone <your-repo-url> ~/docker/big-tech-news
cd ~/docker/big-tech-news

# 2. Seed archive.db as a file (Docker would create it as a directory otherwise)
touch data/archive.db

# 3. Build and start
docker compose up -d --build

# 4. Authenticate Claude Code (one-time)
docker exec -it bigtechnews-app bash
claude login
exit
```

The app container runs `fetch.py --days 2` on startup (catches up any
missed runs) and then daily at 06:00 via cron. Fetches are idempotent.

**Add to nginx-proxy-manager:** create a new Proxy Host for your domain,
forward to `localhost:4003`, enable SSL via Let's Encrypt.

**Generating a digest over SSH:**

```bash
ssh pi
docker exec -it bigtechnews-app bash
# now inside the container:
claude
# → "Give me this week's digest."
```

The rendered HTML is immediately live at your domain.

**Fetch logs:**

```bash
docker exec bigtechnews-app tail -f /app/launchd/fetch.log
```

---

## Deployment: macOS (local)

For local use without a Pi, run directly with a Python venv and launchd.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python fetch.py --days 14    # backfill the last 2 weeks
```

**Daily fetch (launchd):**

```bash
REPO="$(pwd)"
sed "s|{{REPO}}|$REPO|g" launchd/com.example.bigtechnews.plist.template \
  > ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
launchctl load ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
```

Runs at 06:00 local time. To disable:

```bash
launchctl unload ~/Library/LaunchAgents/com.yourname.bigtechnews.plist
```

**Generating a digest:** open the repo in Claude Code and ask in plain English:

> *"Give me this week's digest."*
> *"Catch me up on the last 4 weeks."*
> *"Generate a digest for the week of March 22."*

---

## How curation works

Claude reads `CLAUDE.md`, queries the archive for unjudged items in the
window, applies the filter taxonomy (include/skip + section assignment),
writes verdicts to the `curation` table, and renders the HTML. Re-running
over the same window reuses prior judgments — only new items are
re-evaluated.

The LLM only **picks and categorizes** items. Every headline and link is
loaded verbatim from the database by `render.py`, so the digest is never
paraphrased or hallucinated.

## Manual digest generation

You can also build a spec by hand and render it directly:

```bash
cat > /tmp/spec.json <<'JSON'
{
  "title": "Week of Apr 5 – Apr 11, 2026",
  "subtitle": "Sun 2026-04-05 → Sat 2026-04-11",
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

CREATE TABLE curation (
  item_id     TEXT PRIMARY KEY,
  verdict     TEXT NOT NULL,         -- 'include' | 'skip'
  section     TEXT,                  -- section name if verdict='include'
  decided_at  TEXT NOT NULL
);
```

Lead items are the canonical "top of the cluster" stories. Curation
defaults to leads only — non-leads are usually secondary coverage and
would create duplicates.

## License

[GPLv3](LICENSE). Fork freely. The filter taxonomy in [CLAUDE.md](CLAUDE.md)
reflects one person's interests — edit it to match yours.
