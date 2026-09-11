# Conductor backup design

The systemd unit `conductor-backup.service` runs the canonical script at
`/usr/local/sbin/run_conductor_backups.sh`. That installed script is sourced
from `scripts/run_conductor_backups.sh` in this repository. The service,
timer, installer, and portable configuration template are also kept here.

The backup deliberately does not rsync the live Immich PostgreSQL data
directory at `/home/danny/immich-app/postgres/`. Copying a running PostgreSQL
data directory is not a consistent backup and can produce rsync code 24
failures.

Instead, each run:

1. Uses `pg_dump --format=custom` inside `immich_postgres`.
2. Saves PostgreSQL roles and permissions with `pg_dumpall --globals-only`.
3. Verifies the custom dump with `pg_restore --list`.
4. Writes a manifest beside each dump describing its restore contract.
5. Keeps 14 days of verified dumps locally.
6. Copies and verifies the dump files on both external backup drives.
7. Excludes the live PostgreSQL data directory from the `/home/danny` rsync.
8. Mirrors the live Immich media library from the expansion drive to the
   portable drive. The expansion-drive copy is not copied back onto itself.

Machine-specific paths are configured in `/etc/conductor-backup.env`, based on
`config/conductor-backup.env.example`. The repository-owned installer can be
run on a replacement machine after Docker, Immich, and the backup drives are
available:

```bash
sudo scripts/install-conductor-backup.sh
```

The resulting backup contains the home-directory configuration, Compose files,
Immich `.env`, verified database dumps, globals, and manifests. It does not
depend on the original machine's `/var/lib` state or on copying a live database
directory.

The Immich media library lives at `/mnt/seagate-expansion-drive/immich-media`
and is mirrored to the portable drive at
`conductor-backup/immich-media`. This gives a replacement machine both the
media and database needed to recover Immich.

To install a repository update into the systemd-used path:

```bash
sudo scripts/install-conductor-backup.sh
sudo systemctl start conductor-backup.service
sudo systemctl status conductor-backup.service --no-pager
```

Restoration requires a matching Immich/PostgreSQL container, then:

```bash
cat immich-YYYY-MM-DD-HHMMSS.globals.sql | docker exec -i immich_postgres psql -U postgres
cat immich-YYYY-MM-DD-HHMMSS.dump | docker exec -i immich_postgres pg_restore -U postgres -d immich --clean --if-exists
```
