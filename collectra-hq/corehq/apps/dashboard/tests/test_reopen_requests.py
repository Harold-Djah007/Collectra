from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID, REQUEST_XMLNS
from corehq.apps.dashboard.reopen_requests import (
    closing_form_for_reopen, request_from_form, validate_reopen_request,
)
from corehq.form_processor.models import XFormInstance


def form(data):
    return SimpleNamespace(form_id='request-id', form_data=data,
                           received_on=datetime(2026, 9, 25, tzinfo=UTC))


def test_worker_request_prepares_safe_supervisor_review():
    request = request_from_form(form({
        'bed_number': 'dry_bed_3', 'batch_start_date': '2026-09-24',
        'existing_batch_name': '26092403', 'reason': 'Closed before measurements were checked.',
    }))
    assert request['form_id'] == 'request-id'
    assert request['bed'] == 'dry_bed_3'
    assert request['date'] == '2026-09-24'
    assert 'Closed before' in request['reason']


def test_invalid_or_empty_request_cannot_enter_supervisor_queue():
    assert request_from_form(form({'bed_number': '99', 'reason': 'Closed accidentally'})) is None
    assert request_from_form(form({'bed_number': 'dry_bed_1', 'reason': ''})) is None


def test_only_active_app_requests_are_eligible_for_approval():
    request = form({'bed_number': 'dry_bed_2', 'reason': 'Closed too early'})
    request.domain = 'safisana'
    request.app_id = APP_ID
    request.xmlns = REQUEST_XMLNS
    request.state = XFormInstance.NORMAL
    validate_reopen_request(request)
    request.xmlns = 'some-other-form'
    with pytest.raises(ValueError):
        validate_reopen_request(request)


def test_reopen_shortcut_only_accepts_one_case_in_closing_submission():
    case_xml = 'http://commcarehq.org/case/transaction/v2'
    xml = (f'<data><reading>47</reading><case xmlns="{case_xml}" case_id="original">'
           '<close/></case></data>').encode()
    closing_form = SimpleNamespace(domain='safisana', state=XFormInstance.NORMAL,
                                   get_xml=lambda: xml)
    tx = SimpleNamespace(revoked=False, form=closing_form)
    case = SimpleNamespace(domain='safisana', type='dryingbed', closed=True,
                           case_id='original', get_closing_transactions=lambda: [tx])
    assert closing_form_for_reopen(case) is closing_form
    closing_form.get_xml = lambda: xml.replace(
        b'</data>', f'<case xmlns="{case_xml}" case_id="another"><close/></case></data>'.encode())
    with pytest.raises(ValueError):
        closing_form_for_reopen(case)
    closing_form.get_xml = lambda: xml.replace(b'<close/>', b'<create/><close/>')
    with pytest.raises(ValueError):
        closing_form_for_reopen(case)
    case.closed = False
    with pytest.raises(ValueError):
        closing_form_for_reopen(case)
