#!/bin/sh
set -eu
umask 077
mkdir -p /backups
while true; do
  stamp=$(date +%Y%m%d_%H%M%S)
  target="/backups/skz_${stamp}.dump"
  if pg_dump --format=custom --file="${target}.partial"; then
    mv "${target}.partial" "$target"
    find /backups -maxdepth 1 -type f -name 'skz_*.dump' -mtime +29 -delete
    echo "Backup completed: ${stamp}"
  else
    echo "Backup failed: ${stamp}" >&2
    rm -f "${target}.partial"
    exit 1
  fi
  sleep 86400
done
