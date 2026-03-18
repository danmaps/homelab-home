# Umami stack

This directory contains a dedicated Docker Compose setup for self-hosted Umami analytics on Conductor.

Quick start:

```bash
cp .env.example .env
# edit .env with strong secrets

docker compose up -d
```

Then manually proxy `analytics.dannymcvey.com` to `127.0.0.1:3002` in the host Caddy config.

Full instructions live in `../docs/umami.md`.
