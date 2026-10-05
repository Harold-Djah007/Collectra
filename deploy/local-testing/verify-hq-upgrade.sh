#!/usr/bin/env bash
# Run after starting the Collectra test preview. Does not apply form upgrades.
set -euo pipefail
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root/collectra-hq"
python_bin="$PWD/.venv/bin/python"
settings_target="$(readlink -f localsettings.py)"
export COLLECTRA_SHARED_DRIVE_ROOT="$(dirname "$settings_target")/sharedfiles"
export COLLECTRA_FORMPLAYER_URL=http://127.0.0.1:18080
report_dir="${COLLECTRA_VERIFY_REPORT_DIR:-$HOME/collectra-hq-verification}"
mkdir -p "$report_dir"

# Fail before the test suite if local infrastructure is unavailable.
"$python_bin" - <<'PY'
import json
import os
from urllib.request import urlopen

import psycopg2
import redis

errors = []
def check(label, probe):
    try:
        probe()
        print(label + ': ready')
    except Exception:
        errors.append(label)
        print(label + ': unavailable')

def postgres_ready():
    connection = psycopg2.connect(
        host='127.0.0.1', port=5432, dbname='postgres',
        user='commcarehq', password='commcarehq', connect_timeout=3,
    )
    connection.close()

def elasticsearch_ready():
    with urlopen('http://127.0.0.1:9200/', timeout=3) as response:
        data = json.load(response)
        if 'version' not in data:
            raise ValueError('Unexpected Elasticsearch response')

def formplayer_ready():
    with urlopen(os.environ['COLLECTRA_FORMPLAYER_URL'] + '/serverup', timeout=3) as response:
        if json.load(response).get('status') != 'ok':
            raise ValueError('Formplayer is not ready')

check('PostgreSQL (5432)', postgres_ready)
check('Redis (6379)', lambda: redis.Redis(
    host='127.0.0.1', port=6379, socket_connect_timeout=3, socket_timeout=3,
).ping())
check('Elasticsearch (9200)', elasticsearch_ready)
check('Formplayer (18080)', formplayer_ready)
if errors:
    raise SystemExit('Verification stopped before tests. Start the local Docker services '
                     'and test preview, then rerun. Unavailable: ' + ', '.join(errors))
PY

"$python_bin" manage.py check
node "$repo_root/deploy/local-testing/test-dashboard-loading.cjs"
node "$repo_root/deploy/local-testing/test-xlsform-preview.cjs"
node "$repo_root/deploy/local-testing/test-gps-entry.cjs"

"$python_bin" -m pytest --reusedb=1 \
    corehq/apps/app_manager/tests/test_excel_form_builder.py \
    corehq/apps/app_manager/tests/test_xlsform_metadata.py \
    corehq/apps/app_manager/tests/test_form_readiness.py \
    corehq/apps/app_manager/tests/test_check_hq_form_readiness.py \
    corehq/apps/app_manager/tests/test_restore_form_xml_cache.py \
    corehq/apps/app_manager/tests/test_stage_safisana_batch_names.py \
    corehq/apps/app_manager/tests/test_stage_safisana_incident_google_form.py \
    corehq/apps/app_manager/tests/test_repair_safisana_operational_questions.py \
    corehq/apps/app_manager/tests/test_stage_safisana_close_only.py \
    corehq/apps/app_manager/tests/test_reconcile_safisana_reopen_request.py \
    corehq/apps/dashboard/tests/test_operational_alerts.py \
    corehq/apps/dashboard/tests/test_dashboard_permissions.py \
    corehq/apps/dashboard/tests/test_reopen_requests.py \
    corehq/apps/dashboard/tests/test_reopen_archive_integration.py

curl -fsS --max-time 10 "$COLLECTRA_FORMPLAYER_URL/serverup" >/dev/null
"$python_bin" manage.py check_hq_form_readiness safisana --validate-xforms \
    --output "$report_dir/form-readiness.json"

"$python_bin" manage.py stale_data_in_es case --domain safisana \
    > "$report_dir/case-index-gaps.tsv"
python3 - "$report_dir/case-index-gaps.tsv" <<'PY'
import csv
import sys
from pathlib import Path

with Path(sys.argv[1]).open(newline='') as stream:
    reader = csv.DictReader(stream, delimiter='\t')
    if not {'Index', 'Doc ID', 'ES Date'}.issubset(reader.fieldnames or []):
        raise SystemExit('Case index audit output was not recognized; inspect the report.')
    gaps = [row for row in reader if row['Index'] == 'cases']
print('Case List missing or outdated entries:', len(gaps))
if gaps:
    raise SystemExit('Case List audit failed. Repair indexing before the demonstration.')
PY

echo "Automated HQ checks passed. Reports: $report_dir"
echo 'Next: run the manual presentation checks in deploy/local-testing/hq-release-checklist.md.'
echo 'No form draft was applied, no build was released, and no database migration was run.'
