# Solo Strava: product contract

## Thesis

**An agentic, single-player Strava:** a private place where every run has a map, context, a story and a longitudinal record. No network effects, social competition, premium features, ads or SaaS. Conductor is the durable source of truth; Apple Health is the recording system. The user controls all outputs and third-party disclosures.

## Definition of "agentic"

An assistant is not a chatbot bolted onto a dashboard. It can inspect recent training history, retrieve the precise GPS route, compare repeats, use weather and terrain context *with cited provenance*, explain an unusual workout, and prepare suggestions. It does not publish locations, change health records, contact people or buy products without a separate allowed policy and explicit approval. The initial MCP capabilities are **read-only by default**.

### Example tasks

- "Map today's run" → fetch latest valid run; verify sync timestamp; draw recorded track; calculate splits, elevation, weather context.
- "Did the heat slow me down?" → align *observed* temps from nearby weather stations with time/location, compare similar routes and gradient. Explain uncertainty in conditioning, stops, weather-station distance and shade.
- "Which trail do I repeat most?" → cluster route shapes using buffered segments/Hausdorff-like similarity, not merely start/end GPS coordinates.
- "Am I getting fitter?" → compare pace/HR/elevation and recovery across comparable trail runs with confidence; avoid diagnostic claims.
- "Design a fun loop for the dogs" → propose an optional route suggestion, separate from recorded activities; observe heat risk, terrain and water access.

## Product surfaces

1. **Today**: latest workout, sync age, important run insights, route map.
2. **Atlas**: geographic footprints colored by run count, selectable route clusters, hillshade/topography, favorite climbs, cumulative miles. Default obscures home start/end when sharing.
3. **Journal**: timeline of actual workouts, AI-written drafts that the runner can accept or edit, photos and private notes.
4. **Progress**: weekly totals, comparable-route pace and heart-rate trends, climbing, streaks (optional), fatigue signals, data provenance.
5. **Agent activity**: transparent tool receipts (what read, when, what location went to an external provider), approve-only mutations, deny-first policies for sensitive health and exact locations.

## MVP (this PR)

Working source and deployment docs for: free Apple Health syncing, private workout storage, safe upstream APIs, a custom route UI, and MCP support for workouts and simplified route coordinates. The MVP is **not** a fully functioning remote ChatGPT connector or a deployed system until the owner performs local configuration and a real route round trip passes.

## Acceptance criteria for next milestones

### Ingest
- Exercise is recorded with default Apple Watch Workout app; no post-run GPX export and no paid services.
- A native iPhone bridge can upload it while foregrounded and retries background sync when iOS permits.
- Route polyline and metadata survive two duplicate syncs and a receiver restart.
- Data sync status and last successful upload are visible in the UI; unsupported permissions report "unavailable" rather than empty.

### Map
- Plot source GPS track, not geocoded endpoints or OSRM directions.
- Overlay elevation profile and per-segment pace where recorded; no fake point-to-point time.
- Display original workout source and all derivation assumptions.
- Private/public redaction is opt-in on export only; never expose personal GPS through a public GitHub deployment.

### Agent
- Read-only MCP with `list_runs`, `get_run`, `get_route`, `get_route_segment_metrics`, `compare_runs`, `get_sync_status`.
- Tools use the same authenticated, rate-limited backend as the UI; separate scoped credentials for agent and ingest.
- Cloud clients must authenticate with a revocable short-lived user authorization token. Never place `PULS_TOKEN` or a raw DB credential in a remote connector.
- Audit log records agent reads and any egress; sensitive route coordinates require location-scoped consent.

### Reliability
- Tagged upstream release, backup/restore drill, health checks, changes and upgrade runbook.
- No dependencies on cloud database, paid API, paid HealthKit sync, or public ingress.
- All important derived stats are reproducible from source data and checked with fixtures.

## Security boundary


a) HealthKit access happens on the iPhone after native consent.

b) PulsHealth ingest is a write-authorized endpoint reachable only on trusted LAN/tailnet.

c) Solo Strava Atlas is a private read-only UI. The current upstream route GET requires an ingest token, which remains server-side. This is a **known least-privilege gap** to eliminate before any public gateway.

d) The stock PulsHealth MCP is read-only for workout metadata and metrics. Solo Strava's GPS MCP adapter currently runs locally over stdio; remote exposure requires proper OAuth rather than opening a bare token-gated API to the internet.

e) This ChatGPT instance can use remote tools only after a supported app/connector is configured and authorized, and cannot directly see home-lab data on a private address.

## Design direction

Editorial, quiet, map-first. Less Strava's social feed, more a personal field notebook plus a powerful GIS and training analyst. Keep charts and map legible at a glance. Use actual data, not gamified guesswork. Use iPhone's native app only as a trusted ingestion bridge.