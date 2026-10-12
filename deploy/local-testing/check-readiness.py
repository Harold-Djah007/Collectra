"""Run selected non-destructive regression checks in the configured HQ environment."""

import os
import unittest
from pathlib import Path

import pytest

root = Path(os.environ['COLLECTRA_READINESS_ROOT'])
names = [
    'corehq.apps.export.tests.test_export_column',
    'corehq.apps.export.tests.test_export_item',
    'corehq.apps.export.tests.test_table_configuration',
    'corehq.apps.reports.tests.test_readable_formdata.ReadableFormdataTest',
    'corehq.apps.reports.tests.test_time_and_date_manipulations',
    'corehq.apps.users.tests.test_user_role.TestStaticRoles',
]
suite = unittest.TestLoader().loadTestsFromNames(names)
result = unittest.TextTestRunner(verbosity=1).run(suite)
if not result.wasSuccessful():
    raise SystemExit(1)
paths = [
    'corehq/apps/dashboard/tests/test_operational_alerts.py',
    'corehq/apps/dashboard/tests/test_dashboard_permissions.py',
    'corehq/apps/dashboard/tests/test_reopen_requests.py',
    'corehq/apps/app_manager/tests/test_xlsform_metadata.py',
    'corehq/apps/app_manager/tests/test_stage_safisana_incident_google_form.py',
    'corehq/apps/hqwebapp/tests/test_collectra_translation_fallback.py',
    'corehq/apps/app_manager/tests/test_form_pages.py',
    'corehq/apps/app_manager/tests/test_local_mobile_urls.py',
]
raise SystemExit(pytest.main(['-c', str(root / 'deploy/local-testing/pytest-unit.ini'), '-q', *paths]))
