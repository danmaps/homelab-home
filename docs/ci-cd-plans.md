# CI/CD plans

## Current decision: server-owned product packaging

The paid-product package build runs on the homelab server. GitHub remains the
source repository, but GitHub Actions and GitHub Release assets are not part
of the delivery path.

The server job is:

```text
cron every 5 minutes
  └─ flock lock
      └─ refresh-product-packages.sh
          ├─ check main commit for each source repo
          ├─ skip unchanged repos using commit markers
          ├─ build and validate the customer ZIP
          ├─ generate a SHA-256 checksum
          └─ install stable artifacts in /srv/dannymcvey-products
```

### Products

| Source repository | Server package |
| --- | --- |
| `danmaps/arcpy-project-starter` | `arcpy-project-starter.zip` |
| `danmaps/arcpy-safety-harness` | `arcpy-safety-harness.zip` |
| `danmaps/GIS-AI-Working-Agreement-Kit` | `gis-ai-working-agreement-kit.zip` |

Each package has a matching `.sha256` file and a hidden commit marker. The
Working Agreement Kit keeps its canonical `scripts/build_package.py`; its
generated `dist/` output is built on the server and is not committed.

## Repository contract

The three product repositories are source-only. They must not contain:

- GitHub publishing workflows
- server cron scripts
- generated customer ZIPs
- generated checksum files

Packaging logic belongs in the server workspace at:

```text
/home/danny/.openclaw/workspace/automation/refresh-product-packages.sh
```

The server automation is versioned in the private OpenClaw workspace backup
repository. Changes to a product on `main` are picked up automatically by the
next cron run after the merge.

## Operational setup

Cron entry:

```cron
*/5 * * * * flock -n /tmp/product-packages-refresh.lock /home/danny/.openclaw/workspace/automation/refresh-product-packages.sh >>/tmp/product-packages-refresh.log 2>&1
```

Production output directory:

```text
/srv/dannymcvey-products
```

The current host requires a one-time permissions adjustment because this
directory is root-owned and the `danny` cron user cannot write to it without
interactive `sudo`. Until that is corrected, the script can be tested against
a writable staging directory with `PRODUCT_PACKAGE_OUTPUT_DIR=/tmp/...`.

## Verification checklist

After merging a product change to `main`:

1. Wait for the five-minute cron interval, or run the script manually.
2. Check `/tmp/product-packages-refresh.log`.
3. Confirm the package commit marker matches the merged commit.
4. Run `sha256sum -c <package>.sha256` in the output directory.
5. Confirm the ZIP with `python3 -m zipfile -t <package>.zip`.

The staging test has verified both the initial build/install path and the
unchanged-commit skip path for all three products.

## Deferred options

If public/customer downloads are needed later, add a server-controlled
download endpoint or publish from the server. Do not reintroduce a dependency
on GitHub Actions artifact storage for the core packaging path.
