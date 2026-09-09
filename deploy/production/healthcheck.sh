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
done

docker compose exec -T web uv run python manage.py check

curl --fail --silent --show-error --location \
    --max-time 30 "https://${COLLECTRA_HOST}/accounts/login/" >/dev/null
curl --fail --silent --show-error \
    --max-time 30 "https://${COLLECTRA_HOST}/formplayer/serverup" >/dev/null

echo "Collectra HQ and Formplayer health checks passed."
