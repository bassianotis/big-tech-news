# Pi Deployment Requirements

**Date:** 2026-04-12
**Status:** Draft

## Goal

Move big-tech-news from the user's Mac to a Raspberry Pi 4 (arm64) running as Docker containers, consistent with all other apps on the Pi. The Pi handles daily fetching automatically. The user SSHes in, `docker exec`s into the app container, and runs Claude Code interactively to curate and render a digest. The resulting HTML is immediately accessible at `news.bassapps.net` via the Pi's existing nginx-proxy-manager.

## Architecture

```
docker-compose (big-tech-news)
├── bigtechnews-app          ← Python + Node.js + Claude Code CLI + cron
│   └── volumes:
│       ├── ./data/archive.db   → /app/archive.db
│       ├── ./data/digests/     → /app/digests/
│       └── ./config/claude/    → /root/.claude   (auth persists across restarts)
│
└── bigtechnews-web          ← nginx:alpine, serves digests/ as static files
    └── volumes:
        └── ./data/digests/  → /usr/share/nginx/html  (read-only)

nginx-proxy-manager (existing)
└── news.bassapps.net → bigtechnews-web:80
```

## Components

### 1. `bigtechnews-app` container

- **Base image:** `python:3.11-slim` (official arm64-compatible image)
- **Installs:** Node.js LTS + Claude Code CLI (`npm install -g @anthropic-ai/claude-code`) + Python deps (`requests`, `beautifulsoup4`, `jinja2`)
- **Cron job:** runs `fetch.py --days 2` daily at 06:00 local time
  - Must use `cron` (or `supercronic`) inside the container with `Persistent`-equivalent behavior — on container start, check if today's fetch has already run; if not, run immediately
- **Entrypoint:** starts cron daemon; container stays alive
- **Claude Code auth:** first-time setup requires `docker exec -it bigtechnews-app bash` then `claude login`; credentials stored in `/root/.claude` which is a named volume — survives container rebuilds

### 2. `bigtechnews-web` container

- **Image:** `nginx:alpine` (tiny, arm64-compatible)
- **Serves:** `digests/` directory as static HTML files
- **Directory listing:** enabled so the user can browse all past digests at `news.bassapps.net`
- **Port:** internal 80, not exposed to host directly — nginx-proxy-manager handles public routing
- **Read-only volume mount** of `./data/digests/`

### 3. nginx-proxy-manager integration

- Add `news.bassapps.net` as a new Proxy Host in the NPM web UI
- Forward to `bigtechnews-web:80` (internal Docker network)
- Enable SSL via Let's Encrypt in NPM (same flow as other apps on the Pi)
- No config file editing needed

### 4. Persistent data

| Path on host | Mounted in container | Purpose |
|---|---|---|
| `./data/archive.db` | `/app/archive.db` (app) | SQLite database |
| `./data/digests/` | `/app/digests/` (app, rw) | Rendered HTML files |
| `./data/digests/` | `/usr/share/nginx/html` (web, ro) | Static serving |
| `./config/claude/` | `/root/.claude` (app) | Claude Code auth token |

### 5. Curation workflow (unchanged)

User SSHes into Pi, then:
```bash
docker exec -it bigtechnews-app bash
cd /app
claude   # interactive curation session, same CLAUDE.md workflow
```

No changes to `fetch.py`, `curate.py`, `render.py`, `CLAUDE.md`, or templates.

### 6. macOS retirement

- Unload Mac launchd job once Pi is confirmed working
- `launchd/` directory stays in repo as reference (the template is still useful for anyone running on Mac)

## Prerequisites

- **Pi OS must be 64-bit (arm64/aarch64).** Required for Node.js LTS and Claude Code.
- **Verify Claude Code `linux-arm64` binary** before building: `npm info @anthropic-ai/claude-code` — confirm a `linux-arm64` binary is in the current release. If absent at build time, Claude Code won't install inside the container and the workflow breaks.
- **`news.bassapps.net` DNS** must resolve to the Pi's public IP (or be handled by your existing DNS setup).

## Non-goals

- No automated curation — Claude stays human-in-the-loop.
- No changes to any existing Python scripts or templates.
- No new nginx config files — NPM web UI handles routing.

## Success criteria

1. `fetch.py` runs automatically at 06:00 daily without user intervention; missed runs execute on next container start.
2. User can `docker exec -it bigtechnews-app bash`, run `claude`, and complete the full curation+render workflow.
3. Generated HTML is live at `news.bassapps.net/YYYY-MM-DD_week.html` immediately after render.
4. `archive.db` and `digests/` survive container rebuilds and Pi reboots.
5. Claude Code auth survives container rebuilds (credential volume).
