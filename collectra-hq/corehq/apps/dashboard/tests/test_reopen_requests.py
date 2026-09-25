from datetime import UTC, datetime
from types import SimpleNamespace

from corehq.apps.dashboard.reopen_requests import request_from_form


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
