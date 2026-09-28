from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from corehq.apps.app_manager.management.commands.reconcile_safisana_reopen_request import (
    Command, verify_previous_reopening,
)
from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID, REQUEST_XMLNS
from corehq.form_processor.models import XFormInstance


def evidence():
    request = SimpleNamespace(domain='safisana', app_id=APP_ID, xmlns=REQUEST_XMLNS,
                              state=XFormInstance.NORMAL, form_id='request',
                              received_on=datetime(2026, 9, 28, 12, 15, tzinfo=UTC),
                              form_data={'bed_number': 'dry_bed_1', 'existing_batch_name': '2026',
                                         'reason': 'Closed by mistake'}, archive=Mock())
    case = SimpleNamespace(domain='safisana', type='dryingbed', name='2026', case_id='original',
                           deleted=False, closed=False,
                           opened_on=datetime(2026, 9, 28, 11, 24, tzinfo=UTC))
    xml = (b'<data><case xmlns="http://commcarehq.org/case/transaction/v2" '
           b'case_id="original"><close/></case></data>')
    closing = SimpleNamespace(domain='safisana', state=XFormInstance.ARCHIVED,
                              get_xml=lambda: xml)
    return request, case, closing


def test_reconciliation_requires_matching_open_case_and_archived_original_close():
    request, case, closing = evidence()
    assert verify_previous_reopening(request, case, closing)['name'] == '2026'
    case.name = 'another batch'
    with pytest.raises(ValueError, match='name must match'):
        verify_previous_reopening(request, case, closing)
    case.name = '2026'
    case.closed = True
    with pytest.raises(ValueError, match='currently open'):
        verify_previous_reopening(request, case, closing)
    case.closed = False
    closing.state = XFormInstance.NORMAL
    with pytest.raises(ValueError, match='already be archived'):
        verify_previous_reopening(request, case, closing)
    closing.state = XFormInstance.ARCHIVED
    closing.get_xml = lambda: (b'<data><case xmlns="http://commcarehq.org/case/transaction/v2" '
                               b'case_id="different"><close/></case></data>')
    with pytest.raises(ValueError, match='exactly one case block'):
        verify_previous_reopening(request, case, closing)


def test_reconciliation_previews_before_archiving_request():
    request, case, closing = evidence()
    with patch('corehq.apps.app_manager.management.commands.reconcile_safisana_reopen_request.'
               'XFormInstance.objects.get_form', side_effect=[request, closing, request, closing]), patch(
                   'corehq.apps.app_manager.management.commands.reconcile_safisana_reopen_request.'
                   'CommCareCase.objects.get_case', return_value=case), patch(
                   'corehq.apps.app_manager.management.commands.reconcile_safisana_reopen_request.'
                   'cache.delete') as clear:
        options = dict(request_id='request', case_id='original', closing_form_id='close',
                       supervisor_id='supervisor')
        Command().handle(**options, apply=False)
        request.archive.assert_not_called()
        clear.assert_not_called()
        Command().handle(**options, apply=True)
        request.archive.assert_called_once_with(user_id='supervisor')
        clear.assert_called_once_with('collectra:reopen-requests:safisana:v1')
