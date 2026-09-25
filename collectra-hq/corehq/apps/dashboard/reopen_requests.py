"""Read-only supervisor review of Safisana worker reopening requests."""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import (
    APP_ID, REQUEST_XMLNS,
)
from corehq.form_processor.models import XFormInstance
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


LOOKBACK_DAYS = 30
MAX_FORMS_PER_DATABASE = 100
MAX_REQUESTS = 30
BED_VALUES = {f'dry_bed_{number}' for number in range(1, 7)} | {'other'}


def request_from_form(form):
    data = form.form_data
    if not isinstance(data, dict):
        return None
    bed = data.get('bed_number')
    reason = data.get('reason')
    if bed not in BED_VALUES or not isinstance(reason, str) or not reason.strip():
        return None
    date = data.get('batch_start_date')
    name = data.get('existing_batch_name')
    return {
        'form_id': form.form_id,
        'bed': bed,
        'date': date[:10] if isinstance(date, str) else '',
        'name': name[:80] if isinstance(name, str) else '',
        'reason': reason.strip()[:500],
        'received_on': form.received_on.isoformat(),
    }


def recent_reopen_requests(domain):
    if domain != 'safisana':
        return []
    cutoff = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    forms = []
    filters = Q(domain=domain, app_id=APP_ID, xmlns=REQUEST_XMLNS,
                state=XFormInstance.NORMAL, received_on__gte=cutoff)
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
