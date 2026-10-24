# Conductor patch and certificate audit

Tracks #17 alongside Slinga #96 and Spatial-Workbench #153. Deadline:
Tuesday October 27, 2026, Pacific time. Keep issues open until live evidence is
complete. No inventory, rebuild or certificate replacement is claimed by this PR.

## 1. Inventory before changing services

Run on Conductor with Docker access, host Python 3 and OpenSSL. Keep reports in
the ignored `audit-evidence/` directory because they describe private services.
Do not commit raw Docker inspect output, environments, or private keys.

Build `audit-evidence/tls-targets.txt` with one `hostname[:port]` per line.
Reconcile it against the **actual** host/container Caddy configs, Tailscale Serve
and Funnel (`tailscale serve status`, `tailscale funnel status`), published ports,
and other reverse proxies. Include `dannymcvey.com`, `workbench.dannymcvey.com`,
`analytics.dannymcvey.com`, and every configured tailnet/public HTTPS name. These
three examples are not an exhaustive list. Inspect `systemctl cat caddy` and its
data directory; pass its actual certificate directory below, not an assumed path.

```bash
mkdir -p audit-evidence
python3 scripts/audit_conductor.py \
  --tls-targets audit-evidence/tls-targets.txt \
  --cert-dir /actual/caddy/certificate-directory \
  > audit-evidence/before.json
```

The audit enumerates every running container directly from Docker, including
internal services and the Umami database. It records image IDs, available registry
digests, runtime versions, health, Compose identity, system CA package versions,
Python certifi/pip stores, Node bundled/effective stores and readable system PEMs.
It never emits container environments or private keys. Base image provenance is
often unavailable in final images and is explicitly marked unknown.

Exit 1 means flagged runtime/store/date evidence. Exit 2 means incomplete/manual
review is required; it is expected until the review below is done. Missing tools,
empty stores, failed TLS checks or changing inventories never count as clean.
The report always requires manual acceptance because probes cannot enumerate
custom application stores, embedded binaries, alternate chains or all listeners.

## 2. Triage every row

Maintain a private table with: container, service owner/Compose path, source
commit, actual Dockerfile/vendor base, old image ID/digest, observed Node/Python/
PHP versions, CA package and bundled-store versions, disposition, rebuilt image
ID/digest, running image ID and health/smoke result. Do not omit databases,
internal services, Umami, or Caddy just because they have no Node executable.

- Node below 22.23.4, 24.22.1 or 26.12.1 on the corresponding supported line,
  EOL Node and unrecognized lines are flagged. Node 24 is this dashboard's line.
- Pre-October 21 system CA/certifi date versions are conservatively flagged.
  Vendor backports may retain an earlier version date: verify release provenance
  and effective trust content rather than assuming age proves vulnerability.
- No readable version or CA store is **unknown**, not absent or safe. Review
  distroless images, non-default PATHs, Java/Go/custom stores, and embedded Node.
- Any PHP runtime needs vendor-specific verification of the October fixes.
- A container creation date cannot prove a fresh base or safe trust store.

## 3. Refresh one service at a time

Pause the dashboard's five-minute deployment cron during this maintenance and
restore it afterwards. Preserve Compose project names, environment, bindings,
volumes and old images for rollback. Back up stateful services using their normal
backup procedure before updates. Do not run volume deletion or global pruning.

For **homelab-home**, this PR replaces Node 20 with `node:24.22.1-alpine`:

```bash
FRESH_BASE=1 bash deploy-pull.sh
```

The script pulls the branch configured in the existing checkout, builds without
cache using a fresh base, recreates only the dashboard, compares its running
image ID to `homelab-home:local`, and checks its runtime. Deploy from a clean
checkout of merged main; do not run the cron concurrently with PR validation.
Normal cron runs retain cached builds. Check the dashboard's configured tailnet
URL and `/api/status` and compare its service list with `before.json` and Docker.

For **Slinga**, follow its #96 PR/runbook and `deploy/deploy.sh`. For
**Spatial Workbench**, follow its #153 runtime/deployment runbook, including the
live `/api/state` verifier. Workbench may be a host systemd service, so inspect
host services/processes too; a container-only list does not cover it.

For other **locally built images**, inspect and update the actual Dockerfile's
base/runtime first, then run the project's Compose command with
`build --pull --no-cache <service>` and `up -d --no-build --force-recreate <service>`.
Capture the built ID, compare it with the running container's `.Image`, rerun
runtime/store probes and the service-specific smoke check. A fresh pull of an
EOL base does not fix an EOL runtime.

For **registry images**, record the current image ID/digest, verify the vendor's
patched runtime/base provenance, pull the selected patched tag/digest and recreate
only that service. The registry owner must rebuild stale vendor images; pulling
an unchanged digest is not evidence of a rebuild. Stop acceptance for any image
without a patched vendor build, and track an owner/action rather than marking it
done.

For **Umami**, inspect both `umami` and `umami-db` from `umami/docker-compose.yml`.
Back up the database first. Select a patched Umami image with a verified Node
version, record/pin its digest, then use that directory's Compose invocation to
pull and recreate one service at a time. Keep the Postgres major version and
named volume; do not upgrade major versions as part of this task. Verify
`pg_isready`, analytics sign-in, event ingestion and the dashboard service entry.

## 4. Certificates and final acceptance

The script verifies hostname and chain with OpenSSL, then resolves the omitted
root using the host trust store and `openssl verify -show_chain`. Inspect the
reported chain and **alternate** chains manually. Stored `.crt`/`.pem` scans
detect the blocked root but cannot reconstruct omitted intermediates. Confirm
all configured certificate directories were readable and populated. Refresh
the host CA packages before relying on its trust decisions.

Replace any served chain ending at **emSign ECC Root CA - G3** under another
trusted hierarchy, validate and reload the actual proxy, then check every name
again. Also inspect Caddy automatic-certificate storage and Tailscale HTTPS names.
TLS errors or a missing hostname leave acceptance incomplete.

Rerun the audit as `after.json`; compare container identities with `before.json`
and reconcile intended replacements. Confirm all services are running/healthy,
each rebuilt image matches its running ID, and the dashboard still enumerates
them correctly. Save each service's application smoke evidence and final
certificate trust anchors. Review all unknown/manual fields before closing #17.

Rollback one service's app/image/config if necessary, retaining persistent data.
A vulnerable runtime or stale trust store is not an acceptable final state;
leave its issue open and fix forward. No automatic fleet-wide rebuild is used
because this repo does not own every service's build context or state lifecycle.
