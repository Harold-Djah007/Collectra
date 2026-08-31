#!/usr/bin/env bash
set -euo pipefail

database="${FORMPLAYER_DATABASE:-formplayer}"

if [[ ! "$database" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
    echo "FORMPLAYER_DATABASE must be a valid PostgreSQL database name."
    exit 1
fi

psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 <<SQL
SELECT format('CREATE DATABASE %I', '$database')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$database')\gexec
SQL
