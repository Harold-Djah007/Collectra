#!/usr/bin/env bash
#
# One-time (idempotent) setup for the Collectra HQ development environment.
#
# This repository is a monorepo. The runnable web application is the Django
# project in `collectra-hq/` (a rebrand of CommCare HQ). It depends on a set of
# backend services (PostgreSQL, CouchDB, Redis, Elasticsearch 6, Zookeeper,
# Kafka, MinIO and Formplayer) which are run as Docker containers via
# `collectra-hq/scripts/docker`.
#
# The script is safe to re-run: every step checks for existing state first.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HQ_DIR="$REPO_ROOT/collectra-hq"

log() { printf '\n=== %s ===\n' "$*"; }

log "Ensuring system packages (docker prerequisites)"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi

log "Installing uv (Python package/venv manager)"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

log "Installing Dart Sass (needed by django-compressor at runtime)"
if [ ! -x "$HOME/.npm-global/bin/sass" ]; then
    mkdir -p "$HOME/.npm-global"
    npm config set prefix "$HOME/.npm-global"
    npm install -g sass
fi
export PATH="$HOME/.npm-global/bin:$PATH"

# Bring up the Docker daemon and the backend service containers.
"$REPO_ROOT/.cursor/start.sh"

log "Installing Python dependencies (uv sync)"
cd "$HQ_DIR"
uv sync --compile-bytecode

log "Installing JavaScript dependencies and building webpack bundles"
yarn install --frozen-lockfile
yarn build

log "Writing local development settings (localsettings.py)"
# localsettings.py is git-ignored; generate it so the host process can reach the
# Docker services published on localhost.
if [ ! -f "$HQ_DIR/localsettings.py" ]; then
    cat > "$HQ_DIR/localsettings.py" <<'PY'
# ruff: noqa
from dev_settings import *

USE_PARTITIONED_DATABASE = False
SERVER_ENVIRONMENT = 'localdev'
BASE_ADDRESS = 'localhost:8000'

ELASTICSEARCH_HOST = 'localhost'
ELASTICSEARCH_PORT = 9200
ELASTICSEARCH_MAJOR_VERSION = 6

KAFKA_BROKERS = ['localhost:9092']

S3_BLOB_DB_SETTINGS = {
    "url": "http://localhost:9980",
    "access_key": "admin-key",
    "secret_key": "admin-secret",
    "config": {"connect_timeout": 3, "read_timeout": 5},
}

FORMPLAYER_URL = 'http://localhost:8080'
FORMPLAYER_INTERNAL_AUTH_KEY = "secretkey"

CELERY_TASK_ALWAYS_EAGER = True
CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'

COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

SECRET_KEY = 'local-dev-insecure-secret-key'
ALLOWED_HOSTS = ['*']
PY
fi

log "Initialising databases (Couch views, Kafka topics, SQL migrations)"
export CCHQ_IS_FRESH_INSTALL=1
uv run python manage.py sync_couch_views
uv run python manage.py create_kafka_topics
# The SQL migrations request a Couch/ES reindex on a fresh install. That reindex
# path calls out to git against the project directory, which does not hold its
# own .git in this monorepo layout, so run migrations with --no-reindex and drive
# the preindex steps directly below.
uv run python manage.py migrate --no-reindex --noinput
uv run python manage.py compilejsi18n

log "Building Couch design docs and Elasticsearch indices"
uv run python manage.py ptop_preindex --reset
uv run python manage.py sync_finish_couchdb_hq

log "Creating the local superuser (admin@example.com / Passw0rd!)"
if ! uv run python manage.py shell -c \
    "from corehq.apps.users.models import WebUser; import sys; sys.exit(0 if WebUser.get_by_username('admin@example.com') else 1)" \
    >/dev/null 2>&1; then
    printf 'Passw0rd!\nPassw0rd!\n' | uv run python manage.py make_superuser admin@example.com
fi

log "Install complete"
