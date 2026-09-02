#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
    echo "Usage: $0 DOMAIN"
    exit 1
fi

domain="$1"
if [[ ! "$domain" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "DOMAIN may contain only lowercase letters, digits, and hyphens."
    exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
source .env
set +a

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_root="${COLLECTRA_BACKUP_DIR}/${domain}-${stamp}"
container_root="/backups/${domain}-${stamp}"
install -d -m 0700 "$backup_root"

echo "Creating logical domain backup for ${domain}..."
docker compose exec -T --user root web \
    uv run python manage.py dump_domain_data "$domain" --dir "$container_root"

echo "Creating PostgreSQL safety backup..."
docker compose exec -T postgres \
    pg_dumpall -U "${POSTGRES_USER:-commcarehq}" \
    | gzip -9 >"$backup_root/postgres-all.sql.gz"

echo "Exporting domain-scoped BlobDB objects..."
docker compose exec -T --user root web \
    uv run python manage.py run_blob_export "$domain" --dir "$container_root"

archive_path="$(find "$backup_root" -maxdepth 1 -type f -name "data-dump-${domain}-*.zip" -print -quit)"
if [[ -z "$archive_path" ]]; then
    echo "Domain backup archive was not created."
    exit 1
fi

blob_archive="$(find "$backup_root" -maxdepth 1 -type f -name "*-${domain}-blobs*.tar.gz" -print -quit)"
if [[ -z "$blob_archive" ]]; then
    echo "Domain BlobDB archive was not created."
    exit 1
fi

unzip -t "$archive_path"
tar -tzf "$blob_archive" >/dev/null
(
    cd "$backup_root"
    find . -type f ! -name SHA256SUMS -print0 \
        | sort -z \
        | xargs -0 sha256sum >SHA256SUMS
    sha256sum -c SHA256SUMS
)
chmod -R go-rwx "$backup_root"

echo "Backup completed: $backup_root"
echo "Copy this directory to encrypted off-host storage."
