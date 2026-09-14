#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [[ ! -f .env ]]; then
    echo "Missing deploy/production/.env. Copy .env.example and configure it first."
    exit 1
fi

set -a
source .env
set +a

min_free_disk_gb=${COLLECTRA_MIN_FREE_DISK_GB:-10}
if [[ ! "$min_free_disk_gb" =~ ^[1-9][0-9]*$ ]]; then
    echo "COLLECTRA_MIN_FREE_DISK_GB must be a positive integer."
    exit 1
fi
available_kb="$(df -Pk "$COLLECTRA_BACKUP_DIR" | awk 'NR == 2 {print $4}')"
required_kb=$((min_free_disk_gb * 1024 * 1024))
if [[ ! "$available_kb" =~ ^[0-9]+$ ]] || (( available_kb < required_kb )); then
    echo "Insufficient free disk space under $COLLECTRA_BACKUP_DIR."
    echo "Required: at least ${min_free_disk_gb} GiB; available: $((available_kb / 1024 / 1024)) GiB."
    exit 1
fi

docker compose ps

required_services=(
    caddy web celery celery-beat pillowtop formplayer postgres couch redis
    elasticsearch6 zookeeper kafka minio
)
for service in "${required_services[@]}"; do
    if [[ "$(docker compose ps --status running --services "$service")" != "$service" ]]; then
        echo "Required service is not running: ${service}"
        exit 1
    fi
    container_id="$(docker compose ps -q "$service")"
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")"
    if [[ "$health_status" == "unhealthy" || "$health_status" == "starting" ]]; then
        echo "Required service is not healthy: ${service} (${health_status})"
        exit 1
    fi
done

docker compose exec -T web uv run python manage.py check

curl --fail --silent --show-error --location \
    --max-time 30 "https://${COLLECTRA_HOST}/accounts/login/" >/dev/null
curl --fail --silent --show-error \
    --max-time 30 "https://${COLLECTRA_HOST}/formplayer/serverup" >/dev/null

echo "Collectra HQ and Formplayer health checks passed."
