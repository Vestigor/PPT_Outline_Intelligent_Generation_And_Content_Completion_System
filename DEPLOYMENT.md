# Production deployment with Docker Compose

This deployment serves:

- User application: `https://ppt.vestigor.top/`
- Administrator application: `https://ppt.vestigor.top/admin/`
- Backend API: `https://ppt.vestigor.top/api/`
- Health check: `https://ppt.vestigor.top/health`

PostgreSQL, Redis, MinIO and the backend are only reachable through the private Docker network. Only ports 80 and 443 are published by Nginx.

## 1. Server prerequisites

- A Linux server with Docker Engine and Docker Compose v2
- DNS `A`/`AAAA` record for `ppt.vestigor.top` pointing to the server
- Inbound TCP ports 80 and 443 allowed by the firewall/security group
- A valid TLS certificate for `ppt.vestigor.top`

## 2. Configure TLS

Place the certificate and private key at:

```text
deploy/certs/fullchain.pem
deploy/certs/privkey.pem
```

The files are mounted read-only and ignored by Git. Restrict the private key permissions:

```bash
chmod 600 deploy/certs/privkey.pem
```

Because this repository may be public on GitHub, certificates must be uploaded manually to the server and must never be committed:

```bash
scp fullchain.pem user@server:/path/to/project/deploy/certs/fullchain.pem
scp privkey.pem user@server:/path/to/project/deploy/certs/privkey.pem
```

## 3. Configure production environment

Create the real configuration from the template:

```bash
cp backend/.env.example backend/.env
```

Replace every `CHANGE_ME` value. Generate the application secret with:

```bash
openssl rand -hex 32
```

Keep these value pairs identical:

- `POSTGRES_PASSWORD` and the password embedded in `DATABASE_URL`
- `REDIS_PASSWORD` and the password embedded in `REDIS_URL`
- `MINIO_ROOT_USER` and `OSS_ACCESS_KEY`
- `MINIO_ROOT_PASSWORD` and `OSS_SECRET_KEY`

The production internal hostnames must remain `postgres`, `redis` and `minio`; do not replace them with `localhost`.

## 4. Build and start

From the repository root:

```bash
docker compose config --quiet
docker compose build
docker compose up -d
docker compose ps
```

The MinIO initialization container creates the configured bucket automatically. The backend runs `alembic upgrade head` before starting Uvicorn.

Inspect startup logs if a service is unhealthy:

```bash
docker compose logs --tail=200 postgres redis minio minio-init backend gateway
```

## 5. Verify deployment

```bash
curl -I http://ppt.vestigor.top
curl -fsS https://ppt.vestigor.top/health
curl -I https://ppt.vestigor.top/admin/
```

Expected results:

- HTTP redirects to HTTPS with status 301.
- `/health` returns JSON containing `"status":"ok"`.
- `/` and `/admin/` return their corresponding SPA pages.

## 6. Grant the first administrator role

Register the first account through the user application, then promote it from the server. Replace `YOUR_USERNAME`:

```bash
docker compose exec postgres psql -U postgres -d ppt_system -c "UPDATE users SET role='super_admin' WHERE username='YOUR_USERNAME';"
```

If `POSTGRES_USER` or `POSTGRES_DB` was changed in `backend/.env`, use those values in the command. Sign out and then sign in at `https://ppt.vestigor.top/admin/`.

## 7. Update the application

Use the deployment script. It always runs `git pull --ff-only` first and then updates only the requested component:

```bash
./deploy/deploy.sh                # complete stack
./deploy/deploy.sh backend        # backend only
./deploy/deploy.sh gateway        # Nginx and both frontends only
./deploy/deploy.sh user           # alias of gateway
./deploy/deploy.sh admin          # alias of gateway
./deploy/deploy.sh backend user   # backend and frontends
./deploy/deploy.sh infra          # PostgreSQL, Redis and MinIO
```

The script does not run `docker compose down`; unrelated services and persistent volumes remain in place. User and administrator frontend files share the gateway image, so updating either frontend rebuilds only that image. Database migrations run automatically when the backend container starts. Review migration notes and back up production data before an upgrade.

## 8. Certificate renewal

Replace `deploy/certs/fullchain.pem` and `deploy/certs/privkey.pem`, then reload Nginx:

```bash
docker compose exec gateway nginx -t
docker compose exec gateway nginx -s reload
```

## 9. Backup

Example PostgreSQL backup:

```bash
docker compose exec -T postgres pg_dump -U postgres -d ppt_system -Fc > ppt_system.dump
```

Also back up the `minio_data` volume because uploaded source documents are stored there. Redis is used for asynchronous task coordination and is not a replacement for database or object-storage backups.

## 10. Stop services

```bash
docker compose down
```

Do not use `docker compose down -v` in production unless permanent deletion of the database, Redis and MinIO volumes is intended.
