# Production Deployment (Linux + Docker + Nginx + HTTPS)

Tested layout: Ubuntu 22.04/24.04, Docker Engine 24+, Docker Compose plugin v2.

## 1. Server preparation

```bash
sudo apt update && sudo apt -y upgrade
# Docker (official repository)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER   # log out/in
# Firewall: SSH, HTTP, HTTPS only
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw enable
```

Point a DNS record (e.g. `payroll.bravado.co.tz`) at the server.

## 2. Application

```bash
git clone <repo-url> /opt/bravado-payroll && cd /opt/bravado-payroll
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(64))"   # use for DJANGO_SECRET_KEY, again for JWT_SIGNING_KEY
nano .env      # set secrets, domain, SMTP, POSTGRES_PASSWORD, BACKUP_ENCRYPTION_PASSPHRASE, RCLONE_REMOTE
chmod 600 .env
```

## 3. TLS certificates

**Let's Encrypt (recommended):**

```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d payroll.bravado.co.tz   # before nginx is running
# in .env:
TLS_CERT_DIR=/etc/letsencrypt/live/payroll.bravado.co.tz
```

The `live/` directory contains symlinks into `archive/`. Mount `/etc/letsencrypt` if your Docker setup does not resolve them, or copy `fullchain.pem` and `privkey.pem` into `docker/nginx/certs/`.

Renewal (cron, e.g. weekly):

```bash
certbot renew --pre-hook "docker compose -f /opt/bravado-payroll/docker-compose.yml stop nginx" \
              --post-hook "docker compose -f /opt/bravado-payroll/docker-compose.yml start nginx"
```

**Internal/testing only:** a self-signed certificate:

```bash
openssl req -x509 -nodes -newkey rsa:2048 -days 365 -subj "/CN=payroll.local" \
  -keyout docker/nginx/certs/privkey.pem -out docker/nginx/certs/fullchain.pem
```

## 4. Start

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
docker compose exec backend python manage.py seed_reference_data
docker compose exec backend python manage.py create_admin --username admin --email admin@bravado.co.tz
```

Then open `https://payroll.bravado.co.tz` and complete: Company settings → Statutory rules (verify) → Organisation → Users.

## 5. Off-site backups (required)

1. `docker run --rm -it -v $PWD/docker/backup/rclone:/config/rclone rclone/rclone config` to create a remote (S3, B2, Google Drive, SFTP to another server, …).
2. Set `RCLONE_REMOTE=<remote>:<bucket/path>` in `.env`, then `docker compose up -d backup`.
3. Run `docker compose exec backup backup.sh` and confirm the file appears off-site.
4. Test a restore into a scratch DB: `docker compose exec backup restore.sh /backups/<file> restore_test`.

## 6. Upgrades

```bash
cd /opt/bravado-payroll
docker compose exec backup backup.sh          # always back up first
git pull
docker compose up -d --build                  # entrypoint runs migrations automatically
```

## 7. Monitoring

- `docker compose ps` / `docker compose logs --since 1h backend nginx backup`
- Health: `curl -fsS https://payroll.bravado.co.tz/api/schema/ -o /dev/null -w '%{http_code}'` (returns 401/200 when up)
- Watch the backup log for the `WARNING: RCLONE_REMOTE not set` message.

## Running without Docker

1. PostgreSQL 16, Python 3.12 venv, `pip install -r backend/requirements.txt`.
2. Export the environment variables from `.env` (including `DATABASE_URL`).
3. `python manage.py migrate && python manage.py collectstatic`.
4. Run Gunicorn under systemd: `gunicorn config.wsgi:application -b 127.0.0.1:8000 --workers 3`.
5. `npm ci && npm run build` in `frontend/`; serve `frontend/dist` and `backend/staticfiles` with the nginx config in `docker/nginx/nginx.conf`, changing `backend:8000` to `127.0.0.1:8000` and the paths.
6. Schedule `scripts/backup.sh` in cron with the `PG*` and `BACKUP_*` variables.
