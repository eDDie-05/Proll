#!/bin/sh
# PostgreSQL backup: custom-format dump, AES-256 encrypted, local retention, off-site copy via rclone.
#
# Required env: PGHOST PGUSER PGPASSWORD PGDATABASE BACKUP_ENCRYPTION_PASSPHRASE
# Optional env: BACKUP_DIR (/backups) BACKUP_RETENTION_DAYS (14) RCLONE_REMOTE (e.g. s3remote:bravado-backups)
#               RCLONE_CONFIG (path to rclone.conf) BACKUP_REMOTE_RETENTION_DAYS (90)
set -eu

BACKUP_DIR="${BACKUP_DIR:-/backups}"
RETENTION="${BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
FILE="$BACKUP_DIR/bravado_payroll-$STAMP.dump.enc"

: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE must be set}"
mkdir -p "$BACKUP_DIR"

echo "[$(date -Is)] Starting backup of $PGDATABASE"
pg_dump --format=custom --no-owner --no-privileges "$PGDATABASE" \
  | openssl enc -aes-256-cbc -pbkdf2 -iter 200000 -salt -pass env:BACKUP_ENCRYPTION_PASSPHRASE -out "$FILE"
sha256sum "$FILE" > "$FILE.sha256"
echo "[$(date -Is)] Wrote $FILE ($(du -h "$FILE" | cut -f1))"

# Local retention
find "$BACKUP_DIR" -name 'bravado_payroll-*.dump.enc*' -mtime +"$RETENTION" -print -delete

# Off-site copy - backups must never exist only on the database server.
if [ -n "${RCLONE_REMOTE:-}" ]; then
  rclone copy "$FILE" "$RCLONE_REMOTE/"
  rclone copy "$FILE.sha256" "$RCLONE_REMOTE/"
  rclone delete "$RCLONE_REMOTE/" --min-age "${BACKUP_REMOTE_RETENTION_DAYS:-90}d" --include 'bravado_payroll-*' || true
  echo "[$(date -Is)] Copied off-site to $RCLONE_REMOTE"
else
  echo "[$(date -Is)] WARNING: RCLONE_REMOTE not set - backup exists only locally. Configure an off-site target."
fi
echo "[$(date -Is)] Backup complete"
