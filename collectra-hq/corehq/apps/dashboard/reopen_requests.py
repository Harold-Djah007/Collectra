"""Read-only supervisor review of Safisana worker reopening requests."""

from datetime import datetime, timedelta

from django.db.models import Q
from django.utils import timezone
from lxml import etree

from casexml.apps.phone.restore_caching import invalidate_restore_cache

from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import (
    APP_ID, REQUEST_XMLNS,
)
from corehq.apps.app_manager.management.commands.inspect_safisana_reopen_case import (
    CASE_XMLNS, without_single_case_close,
)
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


LOOKBACK_DAYS = 30
MAX_FORMS_PER_DATABASE = 100
MAX_REQUESTS = 30
MAX_CANDIDATES = 10
BED_VALUES = {f'dry_bed_{number}' for number in range(1, 7)} | {'other'}


def _request_cursor(form):
    return f'{form.received_on.isoformat()}|{form.form_id}'


def _parse_request_cursor(cursor):
    try:
        received_on, form_id = cursor.rsplit('|', 1)
        received_on = datetime.fromisoformat(received_on)
        if not received_on.tzinfo or not form_id or len(form_id) > 80:
            raise ValueError
    except (AttributeError, ValueError) as error:
        raise ValueError('Invalid request cursor') from error
    return received_on, form_id


def reopen_requests_page(domain, view='pending', cursor=None):
    """Return a bounded queue or one page of handled request history."""
    if view not in ('pending', 'history'):
        raise ValueError('Invalid reopening request view')
    if domain != 'safisana':
        return [], None
    filters = Q(domain=domain, app_id=APP_ID, xmlns=REQUEST_XMLNS,
                state=XFormInstance.NORMAL if view == 'pending' else XFormInstance.ARCHIVED)
    if cursor:
        received_on, form_id = _parse_request_cursor(cursor)
        filters &= (Q(received_on__lt=received_on)
                    | Q(received_on=received_on, form_id__lt=form_id))
    forms = []
    shard_boundaries = []
    for database in get_db_aliases_for_partitioned_query():
        shard_forms = list(XFormInstance.objects.using(database)
                           .filter(filters).order_by('-received_on', '-form_id')[:MAX_FORMS_PER_DATABASE])
        forms.extend(shard_forms)
        if len(shard_forms) == MAX_FORMS_PER_DATABASE:
            shard_boundaries.append((shard_forms[-1].received_on, shard_forms[-1].form_id))
    forms.sort(key=lambda form: (form.received_on, form.form_id), reverse=True)
    boundary = max(shard_boundaries) if shard_boundaries else None
    requests = []
    last_form = None
    for form in forms:
        if boundary and (form.received_on, form.form_id) < boundary:
            return requests, _request_cursor(last_form)
        request = request_from_form(form)
        if request:
            if len(requests) == MAX_REQUESTS:
                return requests, _request_cursor(last_form)
            requests.append(request)
        last_form = form
    return requests, _request_cursor(last_form) if boundary and last_form else None


def request_from_form(form):
    data = form.form_data
    if not isinstance(data, dict):
        return None
    bed = data.get('bed_number')
    reason = data.get('reason')
    if not isinstance(bed, str) or bed not in BED_VALUES or not isinstance(reason, str) or not reason.strip():
        return None
    date = data.get('batch_start_date')
    name = data.get('existing_batch_name')
    return {
        'form_id': form.form_id,
        'status': 'handled' if getattr(form, 'state', None) == XFormInstance.ARCHIVED else 'pending',
        'bed': bed,
        'date': date[:10] if isinstance(date, str) else '',
        'name': name[:80] if isinstance(name, str) else '',
        'reason': reason.strip()[:500],
        'received_on': form.received_on.isoformat(),
    }


def validate_reopen_request(form):
    if (form.domain != 'safisana' or form.app_id != APP_ID
            or form.xmlns != REQUEST_XMLNS or form.state != XFormInstance.NORMAL
            or request_from_form(form) is None):
        raise ValueError('This is not an active Safisana reopening request')


def closing_form_for_reopen(case):
    if case.domain != 'safisana' or case.type != 'dryingbed' or not case.closed:
        raise ValueError('Select an original, closed Safisana drying-bed case')
    closings = [tx for tx in case.get_closing_transactions() if not tx.revoked]
    if len(closings) != 1:
        raise ValueError('The closing history needs manual review in Case List')
    form = closings[0].form
    if form is None or form.domain != case.domain or form.state != XFormInstance.NORMAL:
        raise ValueError('The closing submission is not available for archiving')
    # A closing submission can affect several cases; never archive one from this
    # shortcut if it could also reopen an unrelated case.
    checked = etree.fromstring(without_single_case_close(form.get_xml(), case.case_id))
    if checked.xpath('//*[local-name()="create" and namespace-uri()=$ns]', ns=CASE_XMLNS):
        raise ValueError('The closing form also created a case; review it manually in Case List')
    return form


def archive_closing_form_and_refresh(case, closing_form, supervisor_id):
    closing_form.archive(user_id=supervisor_id)
    # A worker's next sync must receive the reopened case, even if their
    # previous restore was cached while the case was closed.
    invalidate_restore_cache(case.domain)


def closed_case_suggestions(domain, worker_request):
    """Suggest exact-name matches; the supervisor must still verify a case."""
    validate_reopen_request(worker_request)
    name = request_from_form(worker_request)['name'].strip()
    if not name:
        return []
    cases = []
    for database in get_db_aliases_for_partitioned_query():
        cases.extend(CommCareCase.objects.using(database).filter(
            domain=domain, type='dryingbed', closed=True, deleted=False,
            closed_on__isnull=False,
            name__iexact=name,
        ).order_by('-closed_on')[:MAX_CANDIDATES])
    cases.sort(key=lambda case: case.closed_on, reverse=True)
    return [{
        'case_id': case.case_id,
        'name': case.name,
        'opened_on': case.opened_on.isoformat() if case.opened_on else None,
        'closed_on': case.closed_on.isoformat() if case.closed_on else None,
    } for case in cases[:MAX_CANDIDATES]]


def recent_reopen_requests(domain):
    if domain != 'safisana':
        return []
    cutoff = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    forms = []
    filters = Q(domain=domain, app_id=APP_ID, xmlns=REQUEST_XMLNS,
                state__in=(XFormInstance.NORMAL, XFormInstance.ARCHIVED),
                received_on__gte=cutoff)
    for database in get_db_aliases_for_partitioned_query():
        forms.extend(XFormInstance.objects.using(database)
                     .filter(filters).order_by('-received_on')[:MAX_FORMS_PER_DATABASE])
    forms.sort(key=lambda form: form.received_on, reverse=True)
    requests = []
    for form in forms:
        request = request_from_form(form)
        if request:
            requests.append(request)
        if len(requests) == MAX_REQUESTS:
            break
    return requests
