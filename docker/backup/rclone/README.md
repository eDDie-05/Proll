Put an `rclone.conf` here defining your off-site remote (S3, Backblaze B2, Google Drive, SFTP, ...),
then set `RCLONE_REMOTE=<remote-name>:<bucket-or-path>` in `.env`. Never commit `rclone.conf`.
