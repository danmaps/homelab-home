# Solo Strava

> Zero-subscription, private, single-player Strava for Conductor. Workouts first, no social graph.

**Status:** a reviewable, locally tested prototype. Nothing is installed or deployed on Conductor; iPhone-to-server sync has not been tested yet. This branch replaces the earlier Health Auto Export-specific prototype with a free HealthKit-to-self-hosted stack.

## Why PulsHealth rather than our own iOS application?

There is no Apple Health server-side API. Native HealthKit reads happen on iPhone, under user consent. Building and distributing a custom iOS binary (particularly with HealthKit background-delivery entitlements) is harder to do for free from a Windows/Linux development environment. The [PulsHealth iOS app](https://apps.apple.com/us/app/pulshealth/id6757657354) is free on the App Store and can sync **directly to your own server**; you do not need PulsHealth's hosted service, a Mac, or a paid Apple Developer membership to use its prebuilt app.

PulsHealth is Apache-2.0 open source: https://github.com/PulsHealth/pulshealth . The upstream stack already includes HealthKit anchored-query syncing, route points, TimescaleDB, workouts, a viewer, Grafana, a read-only product API and MCP server. Treat its 0.x server as evolving software and use a tagged release rather than `main`.

## Components

```text
Apple Watch / Workout app
         |
         v
Apple Health on iPhone
         |
         v
PulsHealth (free iPhone app, HealthKit read-only)
         |
       VPN / trusted LAN, authenticated upload
         |
         v
Conductor ── PulsHealth upstream Docker stack
            ├── ingest (127.0.0.1:8080 or a trusted LAN/VPN gateway)
            ├── Postgres/TimescaleDB (127.0.0.1:5432)
            ├── product API (127.0.0.1:8081)
            ├── upstream read-only MCP (127.0.0.1:8082)
            ├── upstream viewer (127.0.0.1:3001)
            └── SOLO STRAVA Atlas (127.0.0.1:3498)
                    ├── custom private running dashboard
                    ├── actual HealthKit GPS polylines
                    └── optional stdio MCP adapter for GPS routes
```

> The current PulsHealth upstream MCP tools cover workouts and their metric series, but **do not yet expose GPS route coordinates**. This repo includes a separate local-only MCP adapter for route lists and route polylines. The upstream read-only MCP server is preferable for all other questions.

## Zero-cost Conductor setup (Linux + Docker)

1. On Conductor, follow the [PulsHealth self-hosted quickstart](https://github.com/PulsHealth/pulshealth#quickstart) from a **tagged release**, not `main`:

```bash
# Pick a permanent path that is backed up, e.g. ~/services:
mkdir -p ~/services && cd ~/services
git clone https://github.com/PulsHealth/pulshealth.git
cd pulshealth
git checkout "$(git describe --tags --abbrev=0 --match 'v*')"
scripts/bootstrap.sh --time-zone America/Los_Angeles
```

The script generates secrets and starts the PulsHealth stack. **Do not commit** `pulshealth/server/.env` or the pairing QR. Database backups are disabled by default upstream: enable its backup profile and verify restore before adding personal history.

2. Give the iPhone a private path to ingest. Simplest for a first test (same trusted Wi-Fi):

```bash
# Still in ~/services/pulshealth
scripts/bootstrap.sh --lan
```

This binds ingest on the LAN and uses a bearer token. Do **not** port-forward this into the internet. For ongoing sync away from home, prefer the free Tailscale iPhone app + Tailscale Serve HTTPS, following [upstream networking docs](https://github.com/PulsHealth/pulshealth/blob/main/server/README.md#exposing-the-server). The iPhone must be able to reach the server when it uploads. Background sync timing is best-effort under iOS restrictions; locked-phone access can be deferred.

3. Install **PulsHealth** from the App Store (free). In **Sync → Set Up**, pair using the generated QR code. Grant **Workouts** and **Workout Routes** access, enable desired raw types and tap **Test Connection**. Backfill the last month including October 8, 2026 for the first test; routes can arrive after workout summaries. Check its Sync event log and `/v1/stats` before trusting completeness.

4. Launch the Solo Strava Atlas alongside the upstream stack. From this repository's `solo-strava` folder:

```bash
cp .env.example .env
# Fill in ATLAS_PASSWORD (openssl rand -hex 24) and PulsHealth secrets:
# PULS_API_TOKEN = value of PULS_API_TOKEN in ~/services/pulshealth/server/.env
# PULS_INGEST_TOKEN = value of PULS_TOKEN in that file
# WARNING: ingest token allows writes upstream. Only the server-side Atlas process has it.
docker compose up -d --build
curl -I http://127.0.0.1:3498/  # should demand HTTP Basic auth
```

The Atlas container uses Linux host networking to access PulsHealth's loopback API ports without publishing them. It listens **only** on Conductor's `127.0.0.1:3498`. For iPhone access to the dashboard, use Tailscale Serve HTTPS; don't change its binding to `0.0.0.0` or expose it on the public internet. An optional external map-tile request goes to OpenStreetMap, so the map viewport is visible to that provider. Self-hosting tiles can eliminate this later.

## What the app does today

- Lists recent workouts; click one for its **actual recorded route** on a Leaflet/OpenStreetMap map.
- Displays distance, workout time, pace and energy when the API has them.
- Treats a missing GPS track as pending/unavailable, not an inferred line.
- Keeps API and ingest credentials off the browser. The dashboard requires a strong Basic-auth password **and private TLS transport**.
- Shows the sync status without uploading anything to a third-party analytics service.
- Provides a local stdio MCP route adapter plus the upstream read-only MCP server for fitness analysis.

## MCP: a real tool surface for agents

**Stock PulsHealth MCP:** `server/mcp` of the upstream install exposes read-only tools for workout metadata, daily trends, sleep, heart-rate time series and more. At Conductor, the upstream service binds to `127.0.0.1:8082`; configure an MCP-enabled local agent using `https://<your-tailnet-machine>/mcp` via Tailscale Serve or the stdio Go binary. Authentication stays enabled.

**Solo Strava GPS route tool (local/stdio):** on a machine with Python 3.12+, do:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements-mcp.txt
# export ATLAS_PASSWORD, PULS_API_TOKEN, PULS_INGEST_TOKEN from your PRIVATE local env
python atlas/mcp_server.py
```

It exposes `list_route_workouts` and `get_workout_route(uuid,max_points)`. The latter returns a downsampled GeoJSON LineString with source points only. This process is an MCP stdio server, not a remotely accessible ChatGPT connector. To serve its tools over the public internet safely, build a distinct OAuth-authenticated read-only service in a later milestone; do not expose the ingest token.

**ChatGPT access limitation:** A personal tailnet URL cannot be called directly from ChatGPT cloud services. Upstream documents a private custom GPT Action backed by a **public HTTPS API**; that trades privacy for convenience and should not be enabled by default. Whether custom remote MCP apps can be connected to this ChatGPT account depends on account/feature access. A deployed MCP server is not automatically connected to this chat. The connected ChatGPT Health plugin can read Apple Health workout summaries today, but not the GPS track itself.

## Development and tests

```bash
python -m unittest discover -s tests -v
python -m py_compile atlas/server.py atlas/route_tools.py atlas/mcp_server.py
```

Unit tests stub both upstream PulsHealth endpoints and use synthetic GPS points. No real user Health data is checked into this repository. The current frontend adapter accepts documented GPS coordinates with `lat/lon` and `latitude/longitude`; validate against a live self-hosted PulsHealth release after pairing.

## Milestones

1. **Data pipeline works**: tagged PulsHealth, iPhone paired, genuine workout+route round trip, background-synced on trusted Wi-Fi/VPN; record latency and failures.
2. **Solo Strava web UI**: polish map, accurate pace and splits, elevation profile, sync health. Verify response shape against real API and tests.
3. **Read-only agent access**: authenticate remote MCP with OAuth and add full GPS routes with explicit rate/point limits. Connect to ChatGPT only when an eligible connector capability and secure endpoint are available.
4. **Personal insights**: private best efforts, recurring-route comparisons, heat overlays with source provenance, training load and run notes. Training advice is informational, not medical.
5. **Operations**: backup+restore drill, pinned version updates, service discovery in homelab-home, privacy tests, disaster recovery.

## Security and honest limitations

- No paid services or subscriptions required, beyond hardware, home electricity, and your existing internet connection.
- No public server ports required for iPhone sync when on the same LAN or VPN.
- Do not store HealthKit ingest credentials in public code, browser storage, GitHub Actions logs, or URLs.
- Browser UI needs Basic authentication over **HTTPS** from a trusted Tailscale Serve proxy; Basic auth on plain LAN HTTP exposes its password.
- The ingest token has write capabilities, although Atlas performs only GETs. Later: ask upstream for a route read endpoint on the read-only product API, or add a distinct read-only GPS service/DB role.
- The PulseHealth server is pre-release; test data migration and upgrades with a backup.
- The MVP has not been installed on Conductor and cannot retrieve live data until you pair the free iPhone app.