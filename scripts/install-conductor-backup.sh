#!/usr/bin/env bash
set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run this script with sudo." >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
install -D -m 0755 "${REPO_ROOT}/scripts/run_conductor_backups.sh" /usr/local/sbin/run_conductor_backups.sh
install -D -m 0644 "${REPO_ROOT}/systemd/conductor-backup.service" /etc/systemd/system/conductor-backup.service
install -D -m 0644 "${REPO_ROOT}/systemd/conductor-backup.timer" /etc/systemd/system/conductor-backup.timer

if [[ ! -f /etc/conductor-backup.env ]]; then
  install -D -m 0600 "${REPO_ROOT}/config/conductor-backup.env.example" /etc/conductor-backup.env
  echo "Created /etc/conductor-backup.env; review its paths before running the timer."
fi

systemctl daemon-reload
systemctl enable --now conductor-backup.timer
systemctl list-timers conductor-backup.timer --no-pager
