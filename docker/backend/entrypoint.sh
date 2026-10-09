#!/bin/sh
set -e

echo "Waiting for PostgreSQL..."
until pg_isready -d "$DATABASE_URL" >/dev/null 2>&1; do sleep 2; done

python manage.py migrate --noinput
python manage.py collectstatic --noinput >/dev/null
python manage.py seed_roles

exec "$@"
