#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 DOMAIN FORM_ID"
    exit 1
fi

domain="$1"
form_id="$2"

if [[ ! "$domain" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
    echo "DOMAIN may contain only lowercase letters, digits, and hyphens."
    exit 1
fi

if [[ ! "$form_id" =~ ^[A-Za-z0-9_-]+$ ]]; then
    echo "FORM_ID contains unsupported characters."
    exit 1
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
source .env
set +a

echo "Verifying submission ${form_id} belongs to ${domain}..."

docker compose exec -T \
    -e COLLECTRA_ACCEPTANCE_DOMAIN="$domain" \
    -e COLLECTRA_ACCEPTANCE_FORM_ID="$form_id" \
    web uv run python manage.py shell <<'PY'
import json
import os

from corehq.form_processor.models import XFormInstance
from corehq.form_processor.exceptions import XFormNotFound

expected_domain = os.environ["COLLECTRA_ACCEPTANCE_DOMAIN"]
form_id = os.environ["COLLECTRA_ACCEPTANCE_FORM_ID"]

try:
    form = XFormInstance.objects.get_form(form_id)
except XFormNotFound as exc:
    raise SystemExit(f"FAIL: form is not present locally: {form_id}") from exc

errors = []
if form.domain != expected_domain:
    errors.append(
        f"form belongs to {form.domain!r}, expected {expected_domain!r}"
    )
if form.is_archived:
    errors.append("form is archived")
if not form.initial_processing_complete:
    errors.append("initial processing is incomplete")

result = {
    "form_id": form.form_id,
    "domain": form.domain,
    "received_on": form.received_on.isoformat() if form.received_on else None,
    "server_modified_on": (
        form.server_modified_on.isoformat() if form.server_modified_on else None
    ),
    "app_id": form.app_id,
    "build_id": form.build_id,
    "xmlns": form.xmlns,
    "archived": form.is_archived,
    "initial_processing_complete": form.initial_processing_complete,
}

print(json.dumps(result, indent=2, sort_keys=True))

if errors:
    raise SystemExit("FAIL: " + "; ".join(errors))

print(
    f"PASS: {form_id} was processed successfully in project {expected_domain}."
)
PY
