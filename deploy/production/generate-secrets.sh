#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

if [[ ! -f .env ]]; then
    cp .env.example .env
    echo "Created .env from .env.example"
fi

chmod 0600 .env

gen() {
    openssl rand -hex 32
}

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT

while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
        DJANGO_SECRET_KEY=replace-with*|DJANGO_SECRET_KEY=)
            echo "DJANGO_SECRET_KEY=$(openssl rand -hex 48)"
            ;;
        POSTGRES_PASSWORD=replace-with*|POSTGRES_PASSWORD=)
            echo "POSTGRES_PASSWORD=$(gen)"
            ;;
        COUCHDB_PASSWORD=replace-with*|COUCHDB_PASSWORD=)
            echo "COUCHDB_PASSWORD=$(gen)"
            ;;
        MINIO_ROOT_PASSWORD=replace-with*|MINIO_ROOT_PASSWORD=)
            echo "MINIO_ROOT_PASSWORD=$(gen)"
            ;;
        FORMPLAYER_AUTH_KEY=replace-with*|FORMPLAYER_AUTH_KEY=)
            echo "FORMPLAYER_AUTH_KEY=$(gen)"
            ;;
        *)
            echo "$line"
            ;;
    esac
done < .env > "$tmp"

mv "$tmp" .env
chmod 0600 .env

echo "Secrets generated in deploy/production/.env"
echo "Still edit COLLECTRA_HOST, COLLECTRA_ADMIN_EMAIL, and CADDY_ACME_EMAIL before bootstrap."
