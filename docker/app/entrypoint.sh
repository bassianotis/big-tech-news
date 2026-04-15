#!/bin/bash

# Run fetch immediately on startup so any interval missed while the
# container was down is caught up. fetch.py is idempotent (upsert), so
# re-running on an already-fetched day is always safe.
# Non-fatal: if the network isn't ready yet, cron will catch it at 06:00.
echo "[bigtechnews] startup fetch..."
python /app/fetch.py --days 2 || echo "[bigtechnews] startup fetch failed (will retry at next cron interval)"

# Start cron in the foreground — this keeps the container alive.
echo "[bigtechnews] starting cron..."
exec cron -f
