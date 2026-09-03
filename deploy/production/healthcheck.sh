#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
source .env
set +a

docker compose ps
docker compose exec -T web uv run python manage.py check

curl --fail --silent --show-error --location \
    --max-time 30 "https://${COLLECTRA_HOST}/accounts/login/" >/dev/null
curl --fail --silent --show-error \
    --max-time 30 "https://${COLLECTRA_HOST}/formplayer/serverup" >/dev/null

echo "Collectra HQ and Formplayer health checks passed."
