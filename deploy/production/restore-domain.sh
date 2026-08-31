#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: COLLECTRA_RESTORE_CONFIRM=DOMAIN $0 DOMAIN BACKUP_ZIP"
    exit 1
fi

domain="$1"
if [[ ! "$domain" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "DOMAIN may contain only lowercase letters, digits, and hyphens."
    exit 1
fi

archive_path="$(realpath "$2")"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
source .env
set +a

if [[ "${COLLECTRA_RESTORE_CONFIRM:-}" != "$domain" ]]; then
    echo "Set COLLECTRA_RESTORE_CONFIRM=${domain} to confirm this restore."
    exit 1
fi

backup_root="$(realpath "${COLLECTRA_BACKUP_DIR}")"
case "$archive_path" in
    "$backup_root"/*) ;;
    *)
        echo "The archive must be stored under COLLECTRA_BACKUP_DIR."
        exit 1
        ;;
esac

unzip -t "$archive_path"
container_path="/backups/${archive_path#"$backup_root"/}"
backup_directory="$(dirname "$archive_path")"
blob_archive="$(
    find "$backup_directory" -maxdepth 1 -type f \
        -name "*-${domain}-blobs*.tar.gz" -print -quit
)"

if [[ -z "$blob_archive" ]]; then
    echo "The domain BlobDB archive is missing beside: $archive_path"
    echo "A domain ZIP contains blob metadata, not the form XML and media objects."
    echo "Run export-existing-domain-blobs.sh and copy its archive beside the ZIP."
    exit 1
fi

tar -tzf "$blob_archive" >/dev/null
checksum_verified=false
for checksum_name in BLOB_SHA256SUMS SHA256SUMS; do
    checksum_path="$backup_directory/$checksum_name"
    if [[ -f "$checksum_path" ]] \
        && grep -Fq "${blob_archive##*/}" "$checksum_path"; then
        (
            cd "$backup_directory"
            sha256sum -c "$checksum_name"
        )
        checksum_verified=true
        break
    fi
done

if [[ "$checksum_verified" != true ]]; then
    echo "No checksum manifest verifies the domain BlobDB archive."
    exit 1
fi

container_blob_archive="/backups/${blob_archive#"$backup_root"/}"

echo "Restoring verified domain-scoped BlobDB objects..."
docker compose exec -T --user root web \
    uv run python manage.py run_blob_import "$container_blob_archive"

echo "Loading ${domain} from the verified logical backup..."
docker compose exec -T --user root web \
    uv run python manage.py load_domain_data "$container_path"

echo "Rebuilding derived Elasticsearch indexes from restored source data..."
docker compose exec -T --user root web \
    uv run python manage.py ptop_preindex --reset

echo "Restore completed. Run ./healthcheck.sh and ./verify-domain.sh ${domain} before issuing QR codes."
