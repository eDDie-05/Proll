#!/bin/sh
# Install the cron schedule from BACKUP_SCHEDULE (default 02:30 daily) and run crond in the foreground.
set -e
SCHEDULE="${BACKUP_SCHEDULE:-30 2 * * *}"
env | grep -E '^(PG|BACKUP_|RCLONE_|TZ)' | sed 's/^/export /' > /etc/backup.env
echo "$SCHEDULE . /etc/backup.env; /usr/local/bin/backup.sh >> /proc/1/fd/1 2>&1" > /etc/crontabs/root
echo "Backup schedule: $SCHEDULE"
exec crond -f -l 8
