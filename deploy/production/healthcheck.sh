#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
# shellcheck disable=SC1091
source .env
set +a

docker compose ps
docker compose exec -T web uv run python manage.py check

echo "Checking public login page..."
curl --fail --silent --show-error --location \
    --max-time 30 "https://${COLLECTRA_HOST}/accounts/login/" >/dev/null

echo "Checking Collectra serverup probe..."
serverup_body="$(curl --fail --silent --show-error \
    --max-time 30 "https://${COLLECTRA_HOST}/serverup.txt")"
if [[ "$serverup_body" != "success" && "$serverup_body" != success* ]]; then
    echo "WARN: /serverup.txt returned unexpected body: ${serverup_body:0:120}"
fi

echo "Checking Formplayer..."
curl --fail --silent --show-error \
    --max-time 30 "https://${COLLECTRA_HOST}/formplayer/serverup" >/dev/null

echo
echo "Collectra HQ and Formplayer health checks passed."
echo "Cellular acceptance: open https://${COLLECTRA_HOST}/serverup.txt on a phone with Wi-Fi off."
echo "Then build the field APK:"
echo "  cd ../../commcare-android && ./scripts/build-field-apk.sh https://${COLLECTRA_HOST}"
