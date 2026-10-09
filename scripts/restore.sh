#!/bin/sh
# Restore an encrypted backup produced by backup.sh.
#   restore.sh /backups/bravado_payroll-YYYYMMDD-HHMMSS.dump.enc [target_database]
# The target database is dropped and recreated. Stop the backend first.
set -eu

FILE="${1:?usage: restore.sh <backup-file> [database]}"
TARGET="${2:-$PGDATABASE}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE must be set}"

if [ -f "$FILE.sha256" ]; then
  (cd "$(dirname "$FILE")" && sha256sum -c "$(basename "$FILE").sha256")
fi

printf "This will REPLACE database '%s' with %s. Type the database name to continue: " "$TARGET" "$FILE"
read -r CONFIRM
[ "$CONFIRM" = "$TARGET" ] || { echo "Aborted."; exit 1; }

psql -d postgres -v ON_ERROR_STOP=1 -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TARGET' AND pid <> pg_backend_pid();" >/dev/null
dropdb --if-exists "$TARGET"
createdb "$TARGET"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -pass env:BACKUP_ENCRYPTION_PASSPHRASE -in "$FILE" \
  | pg_restore --no-owner --no-privileges --exit-on-error -d "$TARGET"
echo "Restore of $FILE into $TARGET complete."
