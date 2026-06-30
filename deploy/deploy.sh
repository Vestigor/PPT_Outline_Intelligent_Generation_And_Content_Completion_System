#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

# Every deployment starts by synchronizing the checked-out branch.
git pull --ff-only

usage() {
  cat <<'EOF'
Usage: ./deploy/deploy.sh [component ...]

Components:
  all         Build and update the complete application stack (default)
  backend     Rebuild and replace only the backend container
  gateway     Rebuild and replace only Nginx + both frontend applications
  user        Alias of gateway; user and admin assets share the gateway image
  admin       Alias of gateway; user and admin assets share the gateway image
  postgres    Update/start only PostgreSQL
  redis       Update/start only Redis
  minio       Update/start MinIO and ensure the bucket exists
  infra       Update/start PostgreSQL, Redis and MinIO

Options:
  -h, --help  Show this help

Examples:
  ./deploy/deploy.sh
  ./deploy/deploy.sh backend
  ./deploy/deploy.sh user
  ./deploy/deploy.sh backend gateway
  ./deploy/deploy.sh infra

The script never runs `docker compose down`, so unchanged services and persistent
volumes remain online. Updating a service uses Compose recreation for that service.
EOF
}

if [[ ! -f backend/.env ]]; then
  echo "Error: backend/.env is missing. Copy backend/.env.example and configure it first." >&2
  exit 1
fi

if [[ ! -f deploy/certs/fullchain.pem || ! -f deploy/certs/privkey.pem ]]; then
  echo "Error: TLS certificate files are missing under deploy/certs/." >&2
  echo "Upload fullchain.pem and privkey.pem manually; they are intentionally not stored in Git." >&2
  exit 1
fi

docker compose config --quiet

if [[ $# -eq 0 ]]; then
  set -- all
fi

declare -A requested=()
for component in "$@"; do
  case "$component" in
    -h|--help)
      usage
      exit 0
      ;;
    all|backend|gateway|postgres|redis|minio|infra)
      requested["$component"]=1
      ;;
    user|admin)
      requested[gateway]=1
      ;;
    *)
      echo "Error: unknown component '$component'." >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -n "${requested[all]:-}" ]]; then
  echo "Building and updating the complete stack..."
  docker compose build
  docker compose up -d --remove-orphans
else
  if [[ -n "${requested[infra]:-}" ]]; then
    requested[postgres]=1
    requested[redis]=1
    requested[minio]=1
  fi

  if [[ -n "${requested[postgres]:-}" ]]; then
    echo "Updating PostgreSQL..."
    docker compose pull postgres
    docker compose up -d --no-deps postgres
  fi

  if [[ -n "${requested[redis]:-}" ]]; then
    echo "Updating Redis..."
    docker compose pull redis
    docker compose up -d --no-deps redis
  fi

  if [[ -n "${requested[minio]:-}" ]]; then
    echo "Updating MinIO and checking the object-storage bucket..."
    docker compose pull minio minio-init
    docker compose up -d --no-deps minio
    docker compose up --no-deps minio-init
  fi

  if [[ -n "${requested[backend]:-}" ]]; then
    echo "Rebuilding and replacing only the backend..."
    docker compose build backend
    docker compose up -d --no-deps backend
  fi

  if [[ -n "${requested[gateway]:-}" ]]; then
    echo "Rebuilding and replacing only the gateway/frontends..."
    docker compose build gateway
    docker compose up -d --no-deps gateway
    docker compose exec -T gateway nginx -t
  fi
fi

echo "Current service status:"
docker compose ps

echo "Checking public HTTPS health endpoint..."
for attempt in {1..30}; do
  if curl --fail --silent --show-error --max-time 5 \
    https://ppt.vestigor.top/health >/dev/null; then
    echo "Deployment completed successfully: https://ppt.vestigor.top"
    exit 0
  fi
  if [[ "$attempt" -eq 30 ]]; then
    break
  fi
  sleep 2
done

echo "Error: deployment finished, but the public health check did not become ready." >&2
echo "Inspect logs with: docker compose logs --tail=200 backend gateway" >&2
exit 1
