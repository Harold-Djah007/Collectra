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
report_name="form-xml-verification-${domain}-${stamp}.csv"
host_report="${COLLECTRA_BACKUP_DIR}/${report_name}"
container_report="/backups/${report_name}"

install -d -m 0700 "${COLLECTRA_BACKUP_DIR}"

echo "Checking every ${domain} form for its XML object..."
docker compose exec -T --user root web \
    uv run python manage.py check_forms_have_xml "$domain" "$container_report"

if [[ ! -s "$host_report" ]]; then
    echo "Verification report was not created: $host_report"
    exit 1
fi

docker compose exec -T --user root web chmod 0600 "$container_report"

if tail -n +2 "$host_report" | grep -q .; then
    echo "Domain verification failed. Missing form XML is listed in: $host_report"
    exit 1
fi

echo "Domain verification passed: every ${domain} form has XML."
echo "Report: $host_report"
