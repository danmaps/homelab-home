# Deploy: homelab-home

This host uses **docker-compose** (not `docker compose`).

## Manual deploy
```bash
cd /home/openclaw/.openclaw/workspace/homelab-home
bash deploy-pull.sh
```

## Auto-deploy (cron)
Add to `crontab -e`:
```
*/5 * * * * /home/openclaw/.openclaw/workspace/homelab-home/deploy-pull.sh >/tmp/homelab-home-deploy.log 2>&1
```

## Tailscale access
Bind in `docker-compose.yml` to your Tailscale IP (e.g., `100.87.16.33:3499:3499`).
Then access: `http://100.87.16.33:3499`
