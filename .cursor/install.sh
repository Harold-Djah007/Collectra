#!/usr/bin/env bash
# One-time setup for the collectra-hq dev environment. Re-runnable.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HQ_DIR="$REPO_ROOT/collectra-hq"

step() { printf '\n[setup] %s\n' "$*"; }

step "Installing Docker"
if ! command -v docker >/dev/null 2>&1; then
    curl -fsSL https://get.docker.com | sudo sh
fi

step "Installing uv"
if ! command -v uv >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/uv" ]; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi
export PATH="$HOME/.local/bin:$PATH"

# django-compressor shells out to `sass` to build the Bootstrap 5 styles.
step "Installing Dart Sass"
if [ ! -x "$HOME/.npm-global/bin/sass" ]; then
    mkdir -p "$HOME/.npm-global"
    npm config set prefix "$HOME/.npm-global"
    npm install -g sass
fi
export PATH="$HOME/.npm-global/bin:$PATH"

step "Starting backing services"
"$REPO_ROOT/.cursor/start.sh"

cd "$HQ_DIR"

step "Installing Python dependencies"
uv sync --compile-bytecode

step "Installing JS dependencies and building bundles"
yarn install --frozen-lockfile
yarn build

# localsettings.py is git-ignored; point the host process at the services on localhost.
step "Writing localsettings.py"
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

step "Running migrations"
export CCHQ_IS_FRESH_INSTALL=1
uv run python manage.py sync_couch_views
uv run python manage.py create_kafka_topics
# A fresh install queues a Couch/ES reindex whose git-snapshot step fails here,
# since collectra-hq has no .git of its own. Skip it and preindex directly below.
uv run python manage.py migrate --no-reindex --noinput
uv run python manage.py compilejsi18n

step "Building Couch design docs and Elasticsearch indices"
uv run python manage.py ptop_preindex --reset
uv run python manage.py sync_finish_couchdb_hq

step "Creating superuser admin@example.com"
if ! uv run python manage.py shell -c \
    "import sys; from corehq.apps.users.models import WebUser; sys.exit(0 if WebUser.get_by_username('admin@example.com') else 1)" \
    >/dev/null 2>&1; then
    printf 'Passw0rd!\nPassw0rd!\n' | uv run python manage.py make_superuser admin@example.com
fi

step "Done"
