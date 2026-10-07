from types import SimpleNamespace
from unittest.mock import Mock, patch
from django.test import RequestFactory

import pytest

from corehq.apps.dashboard.views import _can_reopen_from_dashboard, _can_view_dashboard_submissions
from corehq.apps.users.permissions import SUBMISSION_HISTORY_PERMISSION


@pytest.mark.parametrize('query', [{}, {'request_id': ''}, {'request_id': 'a' * 81}])
def test_reopen_candidates_rejects_invalid_request_before_database_lookup(query):
    from corehq.apps.dashboard.views import dashboard_reopen_candidates

    view = dashboard_reopen_candidates
    while hasattr(view, '__wrapped__'):
        view = view.__wrapped__
    request = RequestFactory().get('/reopen-candidates/', query)
    with patch('corehq.apps.dashboard.views._can_reopen_from_dashboard', return_value=True), \
            patch('corehq.apps.dashboard.views.XFormInstance.objects.get_form') as get_form:
        response = view(request, 'safisana')
    assert response.status_code == 400
    get_form.assert_not_called()


@pytest.mark.parametrize('can_view_submissions', [False, True])
def test_aggregate_report_permission_does_not_grant_submission_access(can_view_submissions):
    user = Mock()
    user.can_view_some_reports.return_value = True
    user.can_view_report.return_value = can_view_submissions
    user.can_edit_data.return_value = True
    request = SimpleNamespace(project=SimpleNamespace(name='safisana', is_snapshot=False),
                              couch_user=user, can_access_all_locations=True)
    assert _can_view_dashboard_submissions(request, 'safisana') is can_view_submissions
    user.can_view_report.assert_called_once_with('safisana', SUBMISSION_HISTORY_PERMISSION)
    with patch('corehq.apps.dashboard.views.has_privilege', return_value=True):
        assert bool(_can_reopen_from_dashboard(request, 'safisana')) is can_view_submissions


@pytest.mark.parametrize('edit_data,all_locations', [(False, True), (True, False)])
def test_reopening_requires_edit_permission_and_all_location_access(edit_data, all_locations):
    user = Mock()
    user.can_view_some_reports.return_value = True
    user.can_view_report.return_value = True
    user.can_edit_data.return_value = edit_data
    request = SimpleNamespace(project=SimpleNamespace(name='safisana', is_snapshot=False),
                              couch_user=user, can_access_all_locations=all_locations)
    with patch('corehq.apps.dashboard.views.has_privilege', return_value=True):
        assert not _can_reopen_from_dashboard(request, 'safisana')
