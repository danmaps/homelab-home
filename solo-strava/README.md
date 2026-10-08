# Solo Strava: private Apple Health workout atlas

A **single-player Strava** for Conductor. The iPhone's [Health Auto Export](https://apps.apple.com/us/app/health-auto-export-json-csv/id1115567069) app sends Apple Watch workouts to this self-hosted backend. It preserves GPS routes, deduplicates overlapping syncs by workout ID, and exposes a password-protected route history, GeoJSON, and GPX export.

**Status:** implementation ready for review and local testing. Not deployed, not connected to an iPhone, not yet validated against a real Health Auto Export V2 export. No personal workout data or credentials are in this repository.

## Topology and privacy

```text
Apple Watch -> Apple Health on iPhone -> Health Auto Export
                                     |-- Google Drive automation -> ChatGPT Drive connector (agent retrieval)
                                     \-- REST API automation -> Conductor (this service)
                                                                   |-- SQLite workout library
                                                                   \-- private Leaflet map + GPX/GeoJSON
```

- **Do not expose this service to the open internet.** Bind only to a Tailscale IP or loopback behind an authenticated HTTPS reverse proxy. Tailscale encrypts connections between members of your tailnet.
- Only share the **Workouts** data type, with routes/heart-rate metrics explicitly enabled. Do *not* export all Apple Health data.
- Never commit a `.env`, workout JSON, route, GPX, or SQLite file; geographic tracks can reveal your home and regular patterns.
- The web map loads OpenStreetMap tiles (external tile requests); remove/replace the base layer with locally hosted tiles if you want fully offline/private map viewing.
- Python Basic authentication is appropriate for a private encrypted Tailscale connection, **not plain public HTTP**. Ingestion uses a separate `X-Ingest-Key` secret.
- iOS HealthKit/Background App Refresh restrict unattended export. It runs only when iOS provides background time and the device is unlocked. This is **eventually consistent**, not real-time.
- The app's local MCP server must stay foregrounded. It is a debugging/developer convenience, not a reliable unattended agent link.

## Conductor setup

```bash
cd solo-strava
cp .env.example .env
# Generate TWO different random secrets, for example:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Edit .env; set SOLO_INGEST_KEY and SOLO_READ_PASSWORD, separately.
# For phone-to-host access, set SOLO_BIND_IP to the Tailscale IPv4 of Conductor.
docker compose up -d --build
```

Compose binds to `127.0.0.1:8787` by default, intentionally. Do not leave loopback binding in place if your phone is sending directly to Conductor's tailnet IP. Docker creates its own persistent named volume; you do not need to create/chown any data directory. Confirm `/healthz` before turning on the phone automation. Use `docker compose logs --tail=100` to troubleshoot. Back up the `solo_data` Docker volume privately.

Open `http://<Conductor-tailnet-ip>:8787/` in a Tailscale-connected browser, authenticate with the `SOLO_READ_USER` and `SOLO_READ_PASSWORD` from `.env`, and inspect maps. Do not put either secret in URLs.

## iPhone setup, step 1: ChatGPT-visible exports

Install **Health Auto Export** (Premium or trial for automations). Under **Automations → New Automation → Google**:

1. Connect your **personal Google account** and authorize Apple Health workout access.
2. Name the automation `solo-strava-workouts`.
3. **Data Type = Workouts**, **Include Route Data = ON**, **Include Workout Metrics = ON**, grouping **Minutes**.
4. **Export Format = JSON**, **Version 2**, date grouping **Day**.
5. Enable automatic sync; choose an hourly cadence if offered. Actual upload timing is governed by iOS and may be delayed.
6. Manually export **October 8, 2026** to verify the GPS route and metrics exist in the output. Do not share your entire Health export.

**Important folder correction:** The app normally creates `Health Auto Export/solo-strava-workouts` under Google Drive. It **does not** automatically use the previously created `Workout GPX Inbox` folder. Discover the actual app-generated folder and use it for subsequent ChatGPT searches. You can ignore or delete the old empty inbox later.

Once files arrive, the Google Drive connection in ChatGPT can search/read the JSON on demand. It is not a real-time live API/MCP connection. Ask: **"Map my latest run from Health Auto Export"**.

## iPhone setup, step 2: private REST ingestion

In Health Auto Export, create **another** automation, this time **REST API**:

| Setting | Value |
|---|---|
| URL | `http://<Conductor-tailnet-ip>:8787/api/ingest` |
| Header | `X-Ingest-Key: <SOLO_INGEST_KEY>` (enter as two fields) |
| Data Type | Workouts only |
| Include Route Data | ON |
| Include Workout Metrics | ON, Minutes |
| Format | JSON |
| Export Version | 2 |
| Date Range | Default (previous full day plus today) |
| Frequency | Hourly, if offered |

Install/enable **Tailscale** on the iPhone, using the same tailnet as Conductor. `http://` is limited to the encrypted tailnet, **never port-forward the service**. If iOS app transport restrictions block the HTTP URL, use a Tailscale HTTPS hostname with valid TLS instead. For a reliable first run, use **Manual Export** for October 8 with the iPhone unlocked, review the app's Activity Logs, and verify the database/dashboard updated. Do not assume success until a real JSON payload is ingested.

If you want *only one* automation, use the Google Drive route first. It already satisfies the goal of automatic ingestion **into ChatGPT**; the REST API adds the home-lab library and dashboard.

## API

- `GET /healthz` -> basic server status (no workout data)
- `POST /api/ingest` -> Health Auto Export JSON `{ "data": {"workouts": [...]}}`, with `X-Ingest-Key`
- `GET /api/workouts` -> summaries (HTTP Basic auth)
- `GET /api/workouts/geo` -> summaries + GPS points (HTTP Basic auth)
- `GET /api/workouts/<id>.geojson` -> a workout's geometry (HTTP Basic auth)
- `GET /api/workouts/<id>.gpx` -> a workout's GPX track (HTTP Basic auth)
- `GET /` -> password-protected personal map dashboard (HTTP Basic auth)

Privacy, routes, and identity fields are included in the private database. Export data is never written to logs. Source JSON exports can contain weather and HR metrics; the backend stores the raw JSON for future analysis.

## Example local test

```bash
python3 -m unittest discover -s tests -v
```

Unit tests use only synthetic GPS points, never your personal routes. They verify authentication, basic import, repeat syncing, route persistence, and format conversions.

## Next milestones

1. Test a **real** Health Auto Export JSON Version 2 file; adjust parsing if the app's live payload differs from the docs. Confirm latency and stable IDs across overlapping syncs.
2. Read-only MCP interface for querying the Conductor database. Only expose via an authenticated remote-access layer approved by the user; do not make a public GET URL to private routes.
3. Single-player Strava analytics: segment repeat routes; pace and elevation profiles; gradual progression; environmental context and heat-aware dog-running recommendations.
4. Optional notifications for newly ingested workouts when a reliable notification channel is configured and approved.

Sources: https://help.healthyapps.dev/en/health-auto-export/automations/rest-api/ , https://help.healthyapps.dev/en/health-auto-export/automations/google-drive/ , https://help.healthyapps.dev/en/health-auto-export/export-format/workouts/