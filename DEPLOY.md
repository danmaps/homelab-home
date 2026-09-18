# Deploy: homelab-home

This host uses **docker-compose** (not `docker compose`).

## Manual deploy
```bash
cd /home/openclaw/.openclaw/workspace/homelab-home
bash deploy-pull.sh
```

## Product packaging

The paid-product packaging flow is server-owned and runs independently of
this dashboard container. See [docs/ci-cd-plans.md](docs/ci-cd-plans.md) for
the cron trigger, package outputs, repository contract, and verification
steps.

## Auto-deploy (cron)
Add to `crontab -e`:
```
*/5 * * * * /home/openclaw/.openclaw/workspace/homelab-home/deploy-pull.sh >/tmp/homelab-home-deploy.log 2>&1
```

## Tailscale access
Bind in `docker-compose.yml` to your Tailscale IP (e.g., `100.87.16.33:3499:3499`).
Then access: `http://100.87.16.33:3499`

## Umami analytics stack

Umami is kept separate from the dashboard app.

See:
- `docs/umami.md`
- `umami/docker-compose.yml`

That stack is meant to run on localhost behind Caddy at:
- `https://analytics.dannymcvey.com`
