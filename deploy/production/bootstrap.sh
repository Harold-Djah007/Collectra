#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [[ ! -f .env ]]; then
    echo "Create deploy/production/.env from .env.example before bootstrapping."
    exit 1
fi

set -a
source .env
set +a

chmod 0600 .env

for command in docker curl; do
    if ! command -v "$command" >/dev/null 2>&1; then
        echo "Required command not found: $command"
        exit 1
    fi
done

declare -A seen_secrets=()

for secret_name in \
    DJANGO_SECRET_KEY POSTGRES_PASSWORD COUCHDB_PASSWORD \
    MINIO_ROOT_PASSWORD FORMPLAYER_AUTH_KEY; do
    secret_value="${!secret_name:-}"
    if [[ ${#secret_value} -lt 24 || "$secret_value" == *replace-with* ]]; then
        echo "${secret_name} must be replaced with an independent random secret."
        exit 1
    fi
    if [[ -n "${seen_secrets[$secret_value]:-}" ]]; then
        echo "${secret_name} must not reuse another service's secret."
        exit 1
    fi
    seen_secrets[$secret_value]=1
done

for setting_name in COLLECTRA_WEB_WORKERS COLLECTRA_CELERY_CONCURRENCY; do
    setting_value="${!setting_name:-2}"
    if [[ ! "$setting_value" =~ ^[1-9][0-9]*$ ]]; then
        echo "${setting_name} must be a positive integer."
        exit 1
    fi
done

if [[ "$COLLECTRA_BACKUP_DIR" != /* ]]; then
    echo "COLLECTRA_BACKUP_DIR must be an absolute host path."
    exit 1
fi

if [[ ! "$COLLECTRA_HOST" =~ ^([A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?\.)+[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]]; then
    echo "COLLECTRA_HOST must be a valid fully qualified hostname without a scheme, port, or path."
    exit 1
fi

if [[ ! ${FORMPLAYER_DATABASE:-formplayer} =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "FORMPLAYER_DATABASE must be a valid PostgreSQL database name."
    exit 1
fi

install -d -m 0700 "${COLLECTRA_BACKUP_DIR}"

echo "Building Collectra HQ..."
docker compose build web

echo "Starting persistent backing services..."
docker compose up -d --wait \
    postgres couch redis elasticsearch6 zookeeper kafka minio

echo "Ensuring the Formplayer database exists..."
if ! docker compose exec -T postgres \
    psql -U "${POSTGRES_USER:-commcarehq}" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '${FORMPLAYER_DATABASE:-formplayer}'" \
    | grep -qx 1; then
    docker compose exec -T postgres \
        createdb -U "${POSTGRES_USER:-commcarehq}" "${FORMPLAYER_DATABASE:-formplayer}"
fi

echo "Starting Formplayer and applying its schema migrations..."
docker compose up -d --wait formplayer

echo "Applying database migrations..."
docker compose run --rm web uv run python manage.py migrate --noinput

echo "Synchronizing CouchDB views and Kafka topics..."
docker compose run --rm web uv run python manage.py sync_couch_views
docker compose run --rm web uv run python manage.py create_kafka_topics

echo "Starting Collectra application services..."
docker compose up -d --wait

echo
echo "Collectra production services are running."
echo "URL: https://${COLLECTRA_HOST}"
echo "Create an administrator only if the restored data does not already provide one:"
echo "  docker compose run --rm web uv run python manage.py make_superuser ${COLLECTRA_ADMIN_EMAIL}"
