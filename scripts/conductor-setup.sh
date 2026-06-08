#!/usr/bin/env bash
# Conductor setup script — runs on each new workspace (git worktree).
# Brings in untracked files and installs deps so the agent can build immediately.
set -euo pipefail

ROOT="${CONDUCTOR_ROOT_PATH:-.}"

# 1) Untracked env: reuse the root .env if present, else seed from the example.
if [ -f "$ROOT/.env" ]; then
  cp "$ROOT/.env" .env
else
  cp .env.example .env
fi

# 2) Python deps (uv).
command -v uv >/dev/null 2>&1 || pip install --user uv
uv sync

# 3) Web deps (pnpm).
( cd packages/web && (command -v pnpm >/dev/null 2>&1 || corepack enable) && pnpm install )

# 4) Shared Postgres: one instance on the host, reused by all worktrees.
if command -v docker >/dev/null 2>&1; then
  docker compose up -d db || true
fi

echo "Workspace ready. Run the web app via the Run button or 'make web'."
