#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$here"

set -a
source .env
set +a

echo "Verifying restored Safisana migration totals..."

docker compose exec -T web uv run python manage.py shell <<'PY'
import json

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.models import CommCareCase, XFormInstance

domain = "safisana"

normal_forms = len(
    XFormInstance.objects.get_form_ids_in_domain_by_state(
        domain,
        XFormInstance.NORMAL,
    )
)
archived_forms = len(
    XFormInstance.objects.get_form_ids_in_domain_by_state(
        domain,
        XFormInstance.ARCHIVED,
    )
)
active_cases = len(CommCareCase.objects.get_case_ids_in_domain(domain))
deleted_cases = len(CommCareCase.objects.get_deleted_case_ids_in_domain(domain))

actual = {
    "normal_forms": normal_forms,
    "archived_forms": archived_forms,
    "forms_total": normal_forms + archived_forms,
    "active_cases": active_cases,
    "deleted_cases": deleted_cases,
    "cases_total": active_cases + deleted_cases,
    "applications": len(get_apps_in_domain(domain)),
    "active_workers": CommCareUser.total_by_domain(domain, is_active=True),
    "archived_workers": CommCareUser.total_by_domain(domain, is_active=False),
    "groups": len(Group.ids_by_domain(domain)),
}

expected = {
    "normal_forms": 83672,
    "archived_forms": 463,
    "forms_total": 84135,
    "active_cases": 5330,
    "deleted_cases": 596,
    "cases_total": 5926,
    "applications": 22,
    "active_workers": 33,
    "archived_workers": 56,
    "groups": 3,
}

print(json.dumps({"domain": domain, "actual": actual, "expected": expected}, indent=2))

differences = {
    name: {"expected": expected[name], "actual": actual[name]}
    for name in expected
    if actual[name] != expected[name]
}

if differences:
    raise SystemExit(
        "FAIL: restored Safisana totals differ from the verified final checkpoint: "
        + json.dumps(differences, sort_keys=True)
    )

print("PASS: restored Safisana core totals match the verified final checkpoint.")
PY

echo "Run ./verify-domain.sh safisana next to verify every form XML object."
