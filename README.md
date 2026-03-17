# homelab-home

A small service index for Conductor.

Instead of pretending to be a full uptime monitor, homelab-home is meant to answer three simpler questions:
- what containers/services are running
- how can I reach them
- are they exposed via tailnet, a published port, or internal only

## What it does

- enumerates running Docker containers
- shows each service as its own card
- surfaces the published host/port when one exists
- distinguishes between:
  - **TAILNET**
  - **PUBLISHED PORT**
  - **INTERNAL**
- lets you open or inline-preview reachable services
- can still use optional config metadata for repo links and naming overrides

## What it is not

homelab-home is **not** a strict public uptime monitor.

A service can be healthy and useful even if a naive port probe says otherwise. For example:
- services behind a reverse proxy
- services intended for tailnet-only access
- services with no direct published port
- services that are internal/admin-only

The intention is closer to a **personal service index + access map** than a binary UP/DOWN dashboard.

## Run

```bash
npm install
npm start
```

Default URL:
- http://localhost:3499

## Docker deployment

The included Compose file:
- binds the app to `100.87.16.33:3499`
- mounts `/var/run/docker.sock` so the app can inspect running containers
- adds `host.docker.internal` access for route probing from inside the container

## Configure services

You can optionally provide `config.local.json` (recommended) or `config.json`.

Load order:
- `config.local.json` (if present and valid JSON file)
- `config.json`
- built-in defaults

Use `config.example.json` as a template.

Configured services are merged with discovered Docker services so you can add:
- nicer display names
- repo URLs
- path overrides
- explicit service metadata

## Access labels

### TAILNET
Service is exposed on a Tailscale IP/port.

### PUBLISHED PORT
Service has a host-published port, but may still be reached through some other preferred route (for example a reverse proxy).

### INTERNAL
Service has no published host port and is primarily useful as an internal dependency or admin-only component.

## Notes

- This does not expose anything new to the internet by itself.
- The dashboard is most useful as a jump page and operator index.
- If something looks wrong, treat the labels as hints about access patterns, not absolute truth about public availability.
