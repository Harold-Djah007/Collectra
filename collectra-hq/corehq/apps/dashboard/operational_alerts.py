"""Safisana operation alerts from explicitly flagged form submissions.

Do not infer incidents from an unchecked task or a meter reading: neither
existing form defines what counts as a failure or a safe threshold.
"""

from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from corehq.form_processor.models import XFormInstance
from corehq.sql_db.util import get_db_aliases_for_partitioned_query


SAFISANA_APP_ID = '43599346df8b71c72052e07e42b241cd'
MORNING_XMLNS = 'http://openrosa.org/formdesigner/7292611C-E519-4CA4-A084-97C2D36644A6'
FORMS = {
    MORNING_XMLNS: 'Morning Checks Daily',
    'http://openrosa.org/formdesigner/1C3FE6EF-6263-4DE9-9CA6-444EB945F0EA': 'Metering Round',
}
MORNING_CHECKS = {
    ('airblower', 'airblower_status'): 'Airblower valve',
    ('ou_pressure', 'ou_pressure_chk_status'): 'Pressure device water level',
    ('gas_piping_dig', 'main_gas_valve_chk_status'): 'Digester main gas valve',
    ('gas_piping_dig', 'parallel_digester_valve_chk_status'): 'Digester parallel valve',
    ('gas_piping_dig', 'digester_condense_chk_status'): 'Digester condensate pit',
    ('air_release', 'air_release_chk_status'): 'Air release valve',
    ('gas_piping_chp', 'parallel_valve_chp_chk_status'): 'CHP parallel valves',
    ('gas_piping_chp', 'chp_condense_chk_status'): 'CHP condensate pit',
    ('flare', 'flare_main_chk_status'): 'Flare main valve',
    ('flare', 'flare_sample_valve_status'): 'Flare sample valve',
    ('cntrl_panel', 'cntrl_panel_switch_chk_status'): 'Control panel',
    ('cntrl_panel', 'desul_panel_valve_chk_status'): 'Desulphurization main valve',
}
LOOKBACK_DAYS = 14
MAX_FORMS_PER_DATABASE = 150
MAX_ALERTS = 20


def alert_from_form(form):
    """Return display data for one explicitly flagged, submitted form."""
    data = form.form_data
    checks = []
    if form.xmlns == MORNING_XMLNS:
        for (group, field), label in MORNING_CHECKS.items():
            answer = data.get(group) or {}
            status = answer.get(field) if isinstance(answer, dict) else None
            if status in ('needs_attention', 'not_completed'):
                checks.append(f'{label}: {"Needs attention" if status == "needs_attention" else "Not completed"}')
    if str(data.get('needs_attention', '')).strip().lower() != 'yes' and not checks:
        return None
    severity = data.get('attention_severity')
    if severity not in ('urgent', 'follow_up'):
        severity = 'follow_up'
    note = str(data.get('attention_note') or '').strip()
    return {
        'form_id': form.form_id,
        'form_name': FORMS[form.xmlns],
        'severity': severity,
        'checks': checks,
        'note': note[:300] or 'The worker requested attention. Open the submission for details.',
        'received_on': form.received_on.isoformat(),
    }


def recent_operational_alerts(domain):
    if domain != 'safisana':
        return []
    cutoff = timezone.now() - timedelta(days=LOOKBACK_DAYS)
    forms = []
    filters = Q(domain=domain, app_id=SAFISANA_APP_ID, state=XFormInstance.NORMAL,
                xmlns__in=FORMS, received_on__gte=cutoff)
    for database in get_db_aliases_for_partitioned_query():
        forms.extend(XFormInstance.objects.using(database)
                     .filter(filters).order_by('-received_on')[:MAX_FORMS_PER_DATABASE])
    forms.sort(key=lambda item: item.received_on, reverse=True)
    alerts = []
    for form in forms:
        alert = alert_from_form(form)
        if alert:
            alerts.append(alert)
        if len(alerts) >= MAX_ALERTS:
            break
    return alerts
