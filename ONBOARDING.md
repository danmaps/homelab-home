# Onboarding service init instructions

This repo is no longer trying to be a fake uptime monitor.

`homelab-home` is now best understood as a **service index + access map** for Conductor.
Its job is to answer:

1. what is running
2. how can I reach it
3. what kind of access does it have

That means the setup workflow should optimize for:
- discoverability
- clear access paths
- stable links
- useful metadata

Not for perfect synthetic UP/DOWN checks.

---

## Mental model

A service can be healthy and useful even if a naive probe is inconclusive.

Examples:
- it is only meant for tailnet access
- it is behind Caddy rather than opened directly on a host port
- it is an internal dependency with no public route
- it has a published port but the preferred route is something else

So when adding a service, think in terms of:
- **access type**
- **best link to open**
- **whether it should appear in the dashboard at all**

---

## How services show up

There are two inputs:

### 1. Docker discovery
`homelab-home` inspects running Docker containers and uses that as the base inventory.

This is the primary source of truth for:
- container name
- published host port
- container port

### 2. Optional config metadata
`config.local.json` or `config.json` can layer on:
- nicer names
- explicit paths
- repo URLs
- stable service keys

Config no longer needs to be the entire dashboard inventory. It mainly adds metadata and overrides.

---

## Access labels

The dashboard is trying to show **how to think about access**, not absolute public availability.

### `TAILNET`
Use this when the service is surfaced on a Tailscale IP/port.

### `PUBLISHED PORT`
Use this when Docker publishes a host port directly.
This does **not** mean that direct port access is the preferred user-facing route.

### `INTERNAL`
Use this when the service has no published host port and is mainly a dependency, admin-only component, or internal tool.

### `unverified`
This is a soft warning, not a failure state.
It means there is a plausible route, but it was not confidently confirmed by the dashboard’s lightweight probe.

---

## Recommended workflow for adding a new service

## 1. Decide whether the service belongs in the dashboard

Good candidates:
- user-facing apps
- admin tools you open regularly
- data tools with a useful UI
- supporting services whose presence matters operationally

Usually not necessary:
- throwaway one-offs
- internal-only components with no value as cards
- noisy infrastructure entries unless you actually want them visible

---

## 2. Decide the intended access pattern

Before adding anything, answer:

- Is this meant to be opened through a direct port?
- Is it meant to live behind Caddy?
- Is it tailnet-only?
- Is it internal only?

That answer matters more than whether a port probe happens to succeed.

---

## 3. Run it in Docker when possible

The current dashboard is built around Docker discovery.

Preferred pattern:
- service runs in a container
- published host port if it should be directly reachable
- no published port if it is internal only

That gives homelab-home the best chance of finding it automatically.

---

## 4. Add metadata only when needed

Use `config.local.json` (recommended) or `config.json` when you want to add or override metadata.

Example:

```json
{
  "services": [
    {
      "key": "maps-dannymcvey-com-web-1",
      "name": "maps.dannymcvey.com",
      "path": "/",
      "repoUrl": "https://github.com/danmaps/maps-dannymcvey-com"
    }
  ]
}
```

Use metadata for:
- cleaner display names
- repo links
- path overrides
- stable human-friendly labels

Do **not** assume config should define the whole dashboard by hand anymore.

---

## 5. Rebuild / restart homelab-home after changes

If you change code or config:

```bash
docker compose up -d --build
```

Then reload the dashboard.

---

## 6. Verify with the right questions

Do not ask only:
- “does it say UP?”

Ask instead:
- is the card present?
- is the name clear?
- does the link open the right thing?
- is the access label roughly correct?
- if it says `unverified`, is that acceptable or should the route be clarified?

---

## Fast checklist for a new service

- [ ] Service is actually worth showing in homelab-home
- [ ] Intended access pattern is clear
- [ ] Docker container is running
- [ ] Published port exists if direct access is desired
- [ ] Config metadata added if name/path/repo should be cleaner
- [ ] Dashboard rebuilt/restarted if necessary
- [ ] Open link works the way you expect
- [ ] Card label matches the real access pattern closely enough

---

## Common examples

### Public-ish or direct service
- app has a published port
- dashboard can open it directly
- likely shows as `PUBLISHED PORT`

### Tailnet-oriented service
- service is mainly opened over Tailscale
- likely shows as `TAILNET`

### Internal dependency
- postgres, worker, admin backend, model service
- may have no host port
- should show as `INTERNAL` if shown at all

---

## Design principle

The dashboard should make services easier to understand, not pretend to know more than it does.

Prefer:
- useful labels
- clear links
- honest ambiguity

Over:
- brittle health theater
- fake precision
- screaming red failures for services that are functioning normally in context
