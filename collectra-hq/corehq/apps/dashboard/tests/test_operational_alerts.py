from datetime import UTC, datetime
from types import SimpleNamespace
from unittest import TestCase

from corehq.apps.dashboard.operational_alerts import FORMS, MORNING_XMLNS, alert_from_form


class OperationalAlertTests(TestCase):

    def form(self, xmlns, data):
        return SimpleNamespace(
            form_id='sample-form', xmlns=xmlns, form_data=data,
            received_on=datetime(2026, 9, 24, tzinfo=UTC),
        )

    def test_morning_attention_status_creates_alert_even_without_summary_field(self):
        form = self.form(MORNING_XMLNS, {
            'airblower': {'airblower_status': 'needs_attention'},
            'attention_severity': 'urgent',
            'attention_note': 'The airblower valve is leaking.',
        })
        alert = alert_from_form(form)
        self.assertEqual(alert['severity'], 'urgent')
        self.assertEqual(alert['checks'], ['Airblower valve: Needs attention'])

    def test_unfinished_check_also_requires_follow_up(self):
        form = self.form(MORNING_XMLNS, {
            'flare': {'flare_main_chk_status': 'not_completed'},
            'attention_note': 'Unable to access the flare today.',
        })
        self.assertEqual(alert_from_form(form)['checks'], ['Flare main valve: Not completed'])

    def test_metering_worker_report_creates_alert(self):
        metering_xmlns = next(xmlns for xmlns in FORMS if xmlns != MORNING_XMLNS)
        form = self.form(metering_xmlns, {
            'needs_attention': 'yes', 'attention_severity': 'follow_up',
            'attention_note': 'Generator fuel gauge may be faulty.',
        })
        self.assertIn('fuel gauge', alert_from_form(form)['note'])

    def test_unflagged_form_is_not_an_alert(self):
        form = self.form(MORNING_XMLNS, {
            'needs_attention': 'no',
            'airblower': {'airblower_status': 'completed'},
        })
        self.assertIsNone(alert_from_form(form))
