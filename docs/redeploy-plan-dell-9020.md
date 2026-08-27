# Homelab redeploy plan (Refurb Dell 9020 → Ubuntu Server LTS)

Date: 2026-02-25

Note: This runbook is written to be safe to keep in a public repo. It names a few service repos, but does not include secrets, IPs, or tokens.

## Goal
Move the home lab services to a new machine (refurb Dell 9020) running Ubuntu Server LTS with minimal downtime, minimal surprises, and a clean rollback path.

Services mentioned recently (verify list):
- homelab-home
- kanban
- esrismells
- photobook
- (plus anything else on the current host)

---

## Beacon’s role
I can:
- Draft and maintain the step-by-step runbook
- Help inventory the current machine (services, ports, data dirs, env)
- Generate cutover checklists and rollback steps
- Review configs for safety (firewall, SSH, secrets handling)
- Validate the new machine post-migration (smoke tests, watchdog checks)

---

## Key decisions (make these explicit early)

### 1) Deployment model
You’re coming from PM2 on Windows. On Ubuntu Server, the sane paths are:

- Option A: **systemd units** (recommended to reduce sprawl)
  - one unit per service
  - deterministic, inspectable
  - logs in `journalctl`

- Option B: **PM2 on Linux**
  - familiar, but still a runtime layer

- Option C: **Docker Compose**
  - great when apps are already container-first
  - may be extra work if services are “run node/py from workspace”

Recommendation: start with **systemd** + a consistent `/srv/apps/<name>` layout.

### 2) Storage + backups
Decide:
- single disk vs mirror
- where persistent data lives (recommend: `/srv/apps/<app>/data`)
- backup target (external USB SSD, NAS, etc.)

Recommendation: put persistent data under `/srv` and back up that tree + selected config files.

### 3) Networking
Decide:
- DHCP reservation vs static IP
- reverse proxy (Caddy/Traefik/Nginx) vs direct ports

Recommendation: DHCP reservation + reverse proxy. Keep internal services private; expose only what you must.

---

## Tools to install (new Ubuntu host)

### Base OS and admin
- OpenSSH server
- `ufw`
- `fail2ban` (optional)
- `rsync`, `curl`, `jq`, `git`
- `tmux`

### Observability
- `ncdu`, `htop`
- `smartmontools`, `lm-sensors`

### Remote access
- **Tailscale** (default access path for services)

### Beacon/OpenClaw (you plan to move it here)
- Node.js LTS
- `openclaw` installed globally
- Telegram + other tokens stored outside git (password manager / env)

---

## Risks and mitigations

### Data loss
- take verified backup before cutover
- practice restore on new host first

### Hidden state / duplication (current setup)
- inventory everything (PM2 apps, working dirs, data dirs)
- converge onto a single “source of truth” per service on the new host

### DNS/IP drift
- prefer stable hostnames (Tailscale MagicDNS) over hardcoded IPs

### Secrets drift
- consolidate secrets into per-service env files with tight perms
- never commit secrets

---

## Migration plan (phased)

### Phase 0: Preflight questions
- Current host: Windows 11 + PM2
- Persistent data: local dirs in workspace folders (needs explicit list)
- Downtime tolerance: 30–60 minutes is fine
- Tailscale: yes, for everything
- New host: Dell OptiPlex 9020 MT (i7-4770, SSD), confirm RAM and disk details

Open items:
1) exact PM2 app list + configs
2) explicit per-service data paths
3) which services (if any) must be reachable outside tailnet

### Phase 1: Inventory current machine (no changes)
Deliverable: a table with:
- service name
- how it runs (PM2 command)
- ports
- working directory
- data directory
- env/secrets location

Commands (Windows):
- `pm2 status`
- `pm2 show <app>`

### Phase 2: Build the new Ubuntu host
- install Ubuntu Server LTS
- SSH keys only
- UFW: allow SSH + Tailscale
- install Tailscale
- create `/srv/apps/<service>` layout
- install Node/Python as needed

### Phase 3: Migrate one service at a time
For each service:
1) copy app code + data to `/srv/apps/<service>`
2) create systemd unit + env file
3) start service on a temporary port
4) validate
5) cut over reverse proxy/DNS

Suggested order (low to high risk):
1) kanban
2) photobook
3) homelab-home
4) esrismells

### Phase 4: Cutover and rollback
- final sync
- switch routes
- smoke test
- keep old host intact for 1 week rollback window

---

## Smoke tests
- homepage loads
- auth works
- data present
- logs not spewing errors

---

## Rollback
- switch reverse proxy/DNS back to old host
- restart services on old host
- record what failed and why
