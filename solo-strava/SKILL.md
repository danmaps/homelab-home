---
name: solo-strava
description: Read private Apple Watch workout exports from the user's connected Google Drive and generate route maps, repeat-route comparisons, and training insights. No social network.
---

# Solo Strava agent

1. When the user asks to map or analyze a run, first retrieve recent workouts via the connected Health data if fitness metrics would help. Apple Health workouts may have summaries but not exported GPS tracks.
2. Find the Google Drive folder created by **Health Auto Export**, normally `Health Auto Export/solo-strava-workouts`. Search subfolders and use the currently returned folder IDs. **Do not assume** the previously created `Workout GPX Inbox` is used by the exporter.
3. Retrieve the relevant JSON, typically `{ "data": { "workouts": [...] } }`. Filter by the user's date or pick the most recent workout by its own `start` timestamp. Choose the right workout when multiple activities exist.
4. Health Auto Export Version 2 has workout ID, name, start, end, duration, and optional `distance`, `elevationUp`, `activeEnergyBurned`, `route`. Route points use `latitude`, `longitude`, `altitude`, and `timestamp`. V1 points may use `lat` and `lon`.
5. Build an actual **route polyline** from recorded coordinates, not an inferred routing-service line. Make a GeoJSON/GPX and an interactive HTML map if needed; do not advertise a map with just start/end pins as the full route. State whether elevation, temperature, and pace come from workout metadata, coordinates, or external weather observations.
6. Do not upload personal routes, identifying home coordinates, credentials, or workout JSON into public GitHub repos. Do not create public links to workout datasets.
7. If a recent workout hasn't synced yet, state it is delayed/unavailable rather than guessing its GPS route. The iPhone's app sync is best-effort and runs only when iOS permits. Explain how to check the automation Activity Logs and do a Manual Export.
8. The Conductor backend (when deployed) is in `homelab-home/solo-strava`. Its API is **not** a native ChatGPT connection; without an approved authenticated connector, retrieve the data via Google Drive. Never expose the private API to the public internet just to make chat access possible.
9. For comparisons, group by route similarity, separate moving vs elapsed time when recorded, and account for temperature, hills, surface and dog stops. Avoid presenting a medical diagnosis or unsupported fitness forecasts.

Ask for a one-time iPhone configuration only when the export isn't set up. Otherwise the agent should do the discovery, retrieval, parsing, and mapping.
