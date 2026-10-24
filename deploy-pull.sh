#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$REPO_DIR"

git pull --ff-only

# Build and recreate only the dashboard, preserving its configured binding.
if [[ "${FRESH_BASE:-0}" == "1" ]]; then
  docker compose build --pull --no-cache homelab-home
else
  docker compose build homelab-home
fi
expected_image=$(docker image inspect --format '{{.Id}}' homelab-home:local)
docker compose up -d --no-build --force-recreate homelab-home
test "$(docker inspect --format '{{.Image}}' homelab-home)" = "$expected_image"
docker exec homelab-home node -e 'const [major,minor,patch]=process.versions.node.split(".").map(Number); if(major!==24 || minor<22 || (minor===22 && patch<1)) process.exit(1); console.log(process.versions.node)'
echo "Verified running image: $expected_image"
for attempt in {1..15}; do
  if docker exec homelab-home node -e 'fetch("http://127.0.0.1:3499/api/status", {signal:AbortSignal.timeout(15000)}).then(async r=>{if(!r.ok)throw Error("HTTP "+r.status); const d=await r.json(); if(!d.success || !Array.isArray(d.services))throw Error("Invalid dashboard response")}).catch(e=>{console.error(e.message);process.exitCode=1})'; then
    echo "Dashboard API healthy; verify service-list parity separately."
    exit 0
  fi
  sleep 1
done
echo "Dashboard API failed after restart" >&2
exit 1
