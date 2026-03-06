#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/home/openclaw/.openclaw/workspace/homelab-home"

cd "$REPO_DIR"

git pull --ff-only

# Build and run container (localhost only)
docker-compose up -d --build
