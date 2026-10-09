#!/bin/sh
set -eu

chown -R app:app /app/staticfiles /app/media

exec gosu app "$@"
