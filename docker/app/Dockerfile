FROM python:3.11-slim

# Install system deps: Node.js LTS + cron
RUN apt-get update && apt-get install -y curl cron \
    && curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - \
    && apt-get install -y nodejs \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Install Claude Code. The wrapper package's real binary lives in an
# optional, platform-specific subpackage; install it explicitly so a flaky
# network during build can't silently strip it. TARGETARCH is set by
# buildx (arm64 on the Pi, amd64 elsewhere). Verify the binary works
# before continuing — fail the build loudly if it doesn't.
ARG TARGETARCH
RUN npm install -g \
      @anthropic-ai/claude-code \
      @anthropic-ai/claude-code-linux-${TARGETARCH} \
    && claude --version

WORKDIR /app

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY *.py ./
COPY templates/ templates/
COPY CLAUDE.md .

# CLAUDE.md references .venv/bin/python (for macOS local use).
# Symlink so the same instructions work inside the container.
RUN mkdir -p /app/.venv/bin && ln -s /usr/local/bin/python /app/.venv/bin/python

# Create log directory (volume-mounted in production, but needed if
# the container runs without the mount).
RUN mkdir -p /app/launchd

# Set up cron job (cron.d format — read directly by the cron daemon)
COPY docker/app/crontab /etc/cron.d/bigtechnews
RUN chmod 0644 /etc/cron.d/bigtechnews

COPY docker/app/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
