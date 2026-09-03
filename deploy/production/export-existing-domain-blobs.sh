#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 DOMAIN DESTINATION_DIRECTORY"
    exit 1
fi

domain="$1"
if [[ ! "$domain" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "DOMAIN may contain only lowercase letters, digits, and hyphens."
    exit 1
fi

destination="$(realpath -m "$2")"
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
hq_root="$(realpath "$here/../../collectra-hq")"

install -d -m 0700 "$destination"

echo "Exporting ${domain} BlobDB objects from the existing Collectra HQ..."
(
    cd "$hq_root"
    uv run python manage.py run_blob_export "$domain" --dir "$destination"
)

blob_archive="$(
    find "$destination" -maxdepth 1 -type f \
        -name "*-${domain}-blobs*.tar.gz" -printf '%T@ %p\n' \
        | sort -nr \
        | head -n 1 \
        | cut -d' ' -f2-
)"
if [[ -z "$blob_archive" ]]; then
    echo "The domain BlobDB archive was not created."
    exit 1
fi

tar -tzf "$blob_archive" >/dev/null
(
    cd "$destination"
    sha256sum "${blob_archive##*/}" >BLOB_SHA256SUMS
    sha256sum -c BLOB_SHA256SUMS
)
chmod -R go-rwx "$destination"
echo "Domain BlobDB export completed: $destination"
