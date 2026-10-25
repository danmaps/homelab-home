# Open WebUI healthcheck override

This is a small derived image from the pinned Open WebUI `v0.11.1` image. It
does not change the application, configuration, data volume, or startup
command. It replaces the image's broken `curl | jq` probe with Python's
standard library, which is already installed in the image.

## Build and validate

```bash
docker build --pull --no-cache -t open-webui:healthcheck-v0.11.1 ops/open-webui
docker run --rm --network host --name open-webui-healthcheck-candidate \
  -e PORT=18080 -e HOST=127.0.0.1 \
  open-webui:healthcheck-v0.11.1 bash start.sh
```

The candidate must report `healthy` after startup. Stop its application and
run `/opt/open-webui-healthcheck.py`; it must return nonzero. The production
recreation keeps `--network host`, `--restart unless-stopped`, the existing
`open-webui` volume mounted at `/app/backend/data`, and all existing
environment variables. The probe follows `OPEN_WEBUI_HEALTH_HOST` or the
configured `HOST` bind (wildcard binds are normalized to loopback). Capture
those values privately with `docker inspect`
before replacing the application container.

## Deploy and rollback

Build the image, verify the candidate, then recreate only `open-webui` using
the same name, host network, command (`bash start.sh`), restart policy, and
volume. Keep the previous image ID/tag. Wait for at least three 30-second
healthy intervals, then verify `/health`, login, and an existing data read.

Rollback recreates the same container from the retained vendor image digest
`ghcr.io/open-webui/open-webui:v0.11.1@sha256:6bb1fbe8ab0a3e0456067f493044ffb66a30a65a34be47f6a5862176a370dd16`
with the preserved environment, network, command, and volume. Never remove
the `open-webui` volume as part of this procedure.
