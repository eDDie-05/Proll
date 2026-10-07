FROM postgres:16-alpine
RUN apk add --no-cache rclone openssl tzdata
COPY scripts/backup.sh /usr/local/bin/backup.sh
COPY scripts/restore.sh /usr/local/bin/restore.sh
COPY docker/backup/entrypoint.sh /entrypoint.sh
RUN chmod +x /usr/local/bin/backup.sh /usr/local/bin/restore.sh /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
