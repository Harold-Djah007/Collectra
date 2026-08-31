#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [[ ! -f .env ]]; then
    echo "Missing .env — copy .env.example and run ./generate-secrets.sh first."
    exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

fail=0

require() {
    local name="$1"
    local value="${!name:-}"
    if [[ -z "$value" || "$value" == *replace-with* || "$value" == *example.com* ]]; then
        echo "FAIL: $name is missing or still a placeholder"
        fail=1
    else
        echo "OK: $name"
    fi
}

require COLLECTRA_HOST
require COLLECTRA_ADMIN_EMAIL
require CADDY_ACME_EMAIL
require DJANGO_SECRET_KEY
require POSTGRES_PASSWORD
require COUCHDB_PASSWORD
require MINIO_ROOT_PASSWORD
require FORMPLAYER_AUTH_KEY
require COLLECTRA_BACKUP_DIR

if [[ "${COLLECTRA_HOST}" == *://* || "${COLLECTRA_HOST}" == */* ]]; then
    echo "FAIL: COLLECTRA_HOST must be a bare hostname (no https:// or path)"
    fail=1
fi

if [[ "${COLLECTRA_BACKUP_DIR}" != /* ]]; then
    echo "FAIL: COLLECTRA_BACKUP_DIR must be absolute"
    fail=1
fi

if [[ ${#DJANGO_SECRET_KEY} -lt 48 ]]; then
    echo "FAIL: DJANGO_SECRET_KEY looks too short"
    fail=1
fi

if [[ "$fail" -ne 0 ]]; then
    echo "Environment validation failed."
    exit 1
fi

echo "Environment looks ready for ./bootstrap.sh"
echo "Next: confirm DNS A record for ${COLLECTRA_HOST} points at this server."
