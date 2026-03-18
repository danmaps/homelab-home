# Umami on Conductor

This repo includes a **dedicated, self-hosted Umami stack** for private personal analytics at:

- `https://analytics.dannymcvey.com`

The setup is intentionally simple:

- isolated PostgreSQL database just for Umami
- Umami bound to **localhost only** on the host (`127.0.0.1:3002` by default)
- public access handled by the existing Caddy reverse proxy
- no coupling to the existing `postgres-lab-db` container

## Files

- `umami/docker-compose.yml` — Umami + dedicated Postgres
- `umami/.env.example` — required secrets and local settings

## 1) Create secrets / env

From the repo root:

```bash
cd umami
cp .env.example .env
```

Edit `umami/.env` and set strong values for:

- `POSTGRES_PASSWORD`
- `APP_SECRET`

Example secret generation:

```bash
openssl rand -base64 32
```

Notes:

- `APP_SECRET` should be a long random string.
- `POSTGRES_PASSWORD` should be unique to Umami.
- `UMAMI_PORT=3002` is a good fit here because the host already uses 3000 and 3001 for other apps.

## 2) Bring Umami up

```bash
cd /home/danny/.openclaw/workspace/homelab-home/umami
docker compose up -d
```

Check status:

```bash
docker compose ps
docker compose logs -f umami
```

Local verification on the host:

```bash
curl -I http://127.0.0.1:3002
```

## 3) Wire Caddy for analytics.dannymcvey.com

Do **not** edit Caddy from this repo automatically. Add a site block manually in the active Caddy config at `/home/danny/caddy/Caddyfile`.

Recommended block:

```caddy
analytics.dannymcvey.com {
    reverse_proxy 127.0.0.1:3002
}
```

Then reload/restart Caddy using your normal host workflow.

Why localhost binding?

- Umami is not directly exposed on a public host port
- Caddy is the only intended internet-facing entry point
- this is a cleaner default for an admin-ish internal service

## 4) Initial admin setup

After Caddy is pointing at Umami, open:

- `https://analytics.dannymcvey.com`

Umami creates a default login on first startup:

- username: `admin`
- password: `umami`

Immediately after first login:

1. change the admin password
2. optionally rename the admin account
3. create a separate daily-use account if you want to avoid using the bootstrap admin all the time

## 5) Add sites in Umami

Inside Umami, create one website entry for each property you want to track:

- `dannymcvey.com`
- `maps.dannymcvey.com`
- `apps.dannymcvey.com`

For each site, Umami will give you a **Website ID** and a tracking script snippet.

## 6) Add the tracking script to your sites

Use the Umami script URL served from your own domain, not from a third party.

Base script URL:

```html
<script defer src="https://analytics.dannymcvey.com/script.js" data-website-id="REPLACE_WITH_UMAMI_WEBSITE_ID"></script>
```

### dannymcvey.com

Add the script in the main HTML template or shared layout, just before `</head>`.

### maps.dannymcvey.com

Add the same script to the shared page shell/layout used by the maps app.

### apps.dannymcvey.com

Add the script to the shared layout/template for the apps surface.

If any app is a SPA, add the base script once globally, then verify pageview behavior in Umami. If route changes are not appearing as expected, enable Umami's SPA-friendly tracking pattern in that app's main client entry.

## 7) Optional: show analytics in homelab-home

If you want Umami to appear as a dashboard card, add an entry to `config.local.json` based on the example in `config.example.json`.

Suggested values:

- key: `umami`
- name: `Umami Analytics`
- publicUrl: `https://analytics.dannymcvey.com`

## Privacy / hardening notes

This is already a relatively privacy-respecting choice compared with third-party analytics, but a few basics still matter:

- keep Umami behind your own domain and infra
- leave the database private on the Docker network only
- keep Umami bound to `127.0.0.1` so only Caddy reaches it directly
- use strong unique `POSTGRES_PASSWORD` and `APP_SECRET`
- change the default admin password immediately
- keep the stack updated with `docker compose pull && docker compose up -d`
- back up the Umami Postgres volume if the analytics history matters to you

## Updating later

```bash
cd /home/danny/.openclaw/workspace/homelab-home/umami
docker compose pull
docker compose up -d
```

## Backup idea

A simple logical backup command:

```bash
docker exec umami-db pg_dump -U umami umami > umami-backup-$(date +%F).sql
```

If you changed the DB/user names in `.env`, adjust that command accordingly.
