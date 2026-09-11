#!/usr/bin/env bash
set -euo pipefail

CONFIG_FILE="${CONDUCTOR_BACKUP_CONFIG:-/etc/conductor-backup.env}"
SOURCE_DIR="/home/danny/"
BACKUP_TARGETS=$'/mnt/seagate-portable-2tb/conductor-backup/home-danny\n/mnt/seagate-expansion-drive/conductor-backup/home-danny'
IMMICH_DUMP_DIR="/var/lib/conductor-backup/immich"
IMMICH_MEDIA_SOURCE="/mnt/seagate-expansion-drive/immich-media"
IMMICH_MEDIA_TARGET="/mnt/seagate-portable-2tb/conductor-backup/immich-media"
IMMICH_CONTAINER="immich_postgres"
IMMICH_RETENTION_DAYS=14
LOG_FILE="/var/log/conductor-backup.log"
LOCK_FILE="/var/lock/conductor-backup.lock"
STATE_DIR="/var/lib/conductor-backup"
STATE_FILE="${STATE_DIR}/status.env"

# All machine-specific values are overrideable in /etc/conductor-backup.env.
# This keeps the recovery procedure portable to a replacement host.
if [[ -f "${CONFIG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CONFIG_FILE}"
fi

mapfile -t TARGETS <<< "${BACKUP_TARGETS}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script as root." >&2
  exit 1
fi

mkdir -p "$(dirname "${LOG_FILE}")" "${STATE_DIR}" "${IMMICH_DUMP_DIR}"
touch "${LOG_FILE}"

exec 9>"${LOCK_FILE}"
if ! flock -n 9; then
  echo "Backup already running." | tee -a "${LOG_FILE}"
  exit 1
fi

timestamp() { date +"%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(timestamp)] $*" | tee -a "${LOG_FILE}"; }

set_state() {
  cat > "${STATE_FILE}" <<EOF
LAST_RUN_DATE=${RUN_DATE}
LAST_RUN_START=${RUN_START}
LAST_RUN_END=$(date -Iseconds)
LAST_RUN_STATUS=$1
LAST_RUN_ERROR=$(printf '%q' "$2")
EOF
}

fail() {
  local message="$1"
  log "${message}"
  set_state "failure" "${message}"
  exit 1
}

ensure_mounted() {
  local mount_path="$1"
  if ! mountpoint -q "${mount_path}"; then
    log "Mounting ${mount_path}."
    mount "${mount_path}"
  fi
  if ! mountpoint -q "${mount_path}"; then
    fail "Mount failed for ${mount_path}."
  fi
}

if ! command -v rsync >/dev/null 2>&1; then fail "rsync is not installed."; fi
if ! command -v docker >/dev/null 2>&1; then fail "docker is not installed."; fi
if ! docker inspect "${IMMICH_CONTAINER}" >/dev/null 2>&1; then fail "Immich PostgreSQL container is missing."; fi

RUN_DATE="$(date +%F)"
RUN_START="$(date -Iseconds)"

create_immich_dump() {
  local suffix="$1"
  local filename="immich-${RUN_DATE}-${suffix}"
  local tmp_dump tmp_globals

  if [[ "$(docker inspect -f '{{.State.Running}}' "${IMMICH_CONTAINER}" 2>/dev/null || true)" != "true" ]]; then
    fail "Immich PostgreSQL container is not running; refusing to create a database backup."
  fi

  tmp_dump="${IMMICH_DUMP_DIR}/.${filename}.dump.tmp"
  tmp_globals="${IMMICH_DUMP_DIR}/.${filename}.globals.sql.tmp"
  rm -f "${tmp_dump}" "${tmp_globals}"

  log "Creating consistent Immich PostgreSQL dump."
  if ! docker exec "${IMMICH_CONTAINER}" pg_dump -U postgres -d immich --format=custom > "${tmp_dump}"; then
    rm -f "${tmp_dump}" "${tmp_globals}"
    fail "Immich pg_dump failed."
  fi
  if ! docker exec "${IMMICH_CONTAINER}" pg_dumpall -U postgres --globals-only > "${tmp_globals}"; then
    rm -f "${tmp_dump}" "${tmp_globals}"
    fail "Immich PostgreSQL globals dump failed."
  fi

  if ! docker exec -i "${IMMICH_CONTAINER}" pg_restore --list - < "${tmp_dump}" >/dev/null 2>&1; then
    rm -f "${tmp_dump}" "${tmp_globals}"
    fail "Immich dump verification failed."
  fi

  chmod 600 "${tmp_dump}" "${tmp_globals}"
  mv -f "${tmp_dump}" "${IMMICH_DUMP_DIR}/${filename}.dump"
  mv -f "${tmp_globals}" "${IMMICH_DUMP_DIR}/${filename}.globals.sql"
  cat > "${IMMICH_DUMP_DIR}/${filename}.manifest.txt" <<EOF
backup_format=postgres-custom-and-globals
created_at=${RUN_START}
database=immich
postgres_container=${IMMICH_CONTAINER}
source_database_path=${SOURCE_DIR%/}/immich-app/postgres
live_database_path_excluded=true
dump_file=${filename}.dump
globals_file=${filename}.globals.sql
restore_validation=pg_restore-list-inside-immich-container
EOF
  chmod 600 "${IMMICH_DUMP_DIR}/${filename}.manifest.txt"
  log "Verified Immich dump ${filename}."
}

RUN_ID="$(date +%Y%m%d-%H%M%S)"
create_immich_dump "${RUN_ID}"

# Keep a short local history so both external targets retain multiple restore points.
find "${IMMICH_DUMP_DIR}" -type f -name 'immich-*.dump' -mtime "+${IMMICH_RETENTION_DAYS}" -delete
find "${IMMICH_DUMP_DIR}" -type f -name 'immich-*.globals.sql' -mtime "+${IMMICH_RETENTION_DAYS}" -delete
find "${IMMICH_DUMP_DIR}" -type f -name 'immich-*.manifest.txt' -mtime "+${IMMICH_RETENTION_DAYS}" -delete

RSYNC_ARGS=(
  --archive --no-owner --no-group --no-perms --omit-dir-times
  --modify-window=1 --delete --delete-excluded --partial --human-readable --itemize-changes
  --exclude=".cache/"
  --exclude=".local/share/Trash/"
  --exclude=".npm/_logs/"
  --exclude=".nvm/alias/lts/\\*"
  --exclude="node_modules/"
  --exclude=".next/cache/"
  --exclude="immich-app/postgres/"
)

log "Backup run started from ${SOURCE_DIR}."
ensure_mounted /mnt/seagate-portable-2tb
ensure_mounted /mnt/seagate-expansion-drive

for target in "${TARGETS[@]}"; do
  mkdir -p "${target}" "${target}/immich-postgres"
  log "Syncing home directory to ${target}."
  if ! rsync "${RSYNC_ARGS[@]}" "${SOURCE_DIR}" "${target}/" >> "${LOG_FILE}" 2>&1; then
    fail "rsync failed while syncing to ${target}."
  fi
  log "Syncing verified Immich database dumps to ${target}/immich-postgres."
  if ! rsync --archive --delete --partial --human-readable --itemize-changes \
      "${IMMICH_DUMP_DIR}/" "${target}/immich-postgres/" >> "${LOG_FILE}" 2>&1; then
    fail "rsync failed while syncing Immich database dumps to ${target}."
  fi
  if ! cmp -s "${IMMICH_DUMP_DIR}/immich-${RUN_DATE}-${RUN_ID}.dump" \
      "${target}/immich-postgres/immich-${RUN_DATE}-${RUN_ID}.dump"; then
    fail "Immich database dump verification failed on ${target}."
  fi
  log "Completed sync to ${target}."
done

# The expansion drive is the live media source, so mirror the library to the
# portable drive only. Copying it to its own drive would not add resilience.
if [[ ! -d "${IMMICH_MEDIA_SOURCE}" ]]; then
  fail "Immich media source is missing: ${IMMICH_MEDIA_SOURCE}."
fi
mkdir -p "${IMMICH_MEDIA_TARGET}"
log "Syncing Immich media library to ${IMMICH_MEDIA_TARGET}."
if ! rsync --archive --delete --partial --human-readable --itemize-changes \
    "${IMMICH_MEDIA_SOURCE}/" "${IMMICH_MEDIA_TARGET}/" >> "${LOG_FILE}" 2>&1; then
  fail "rsync failed while syncing the Immich media library."
fi
log "Completed Immich media library sync."

log "Backup run finished successfully."
set_state "success" "none"
