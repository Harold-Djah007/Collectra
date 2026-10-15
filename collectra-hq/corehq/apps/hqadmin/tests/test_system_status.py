from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase
from kafka.structs import TopicPartition

from pillowtop.utils import PillowConfig, get_all_pillows_json, get_pillow_json


class PillowStatusTests(SimpleTestCase):
    def setUp(self):
        self.configs = [SimpleNamespace(name="broken"), SimpleNamespace(name="healthy")]

    @patch("pillowtop.utils.get_kafka_consumer")
    @patch("pillowtop.utils.get_all_pillow_configs")
    @patch("pillowtop.utils.get_pillow_json")
    def test_one_failed_worker_does_not_hide_healthy_workers(self, get_json, configs, consumer):
        configs.return_value = self.configs
        get_json.side_effect = [ValueError("missing topic"), {"name": "healthy"}]
        rows = get_all_pillows_json(include_errors=True)
        self.assertEqual(rows[0]["name"], "broken")
        self.assertTrue(rows[0]["error"])
        self.assertIsNone(rows[0]["hours_since_last"])
        self.assertEqual(rows[1], {"name": "healthy"})

    @patch("pillowtop.utils.get_kafka_consumer")
    @patch("pillowtop.utils.get_all_pillow_configs")
    @patch("pillowtop.utils.get_pillow_json", side_effect=ValueError("missing topic"))
    def test_metrics_callers_still_receive_failures(self, get_json, configs, consumer):
        configs.return_value = self.configs
        with self.assertRaises(ValueError):
            get_all_pillows_json()

    def test_missing_topic_does_not_attempt_to_fetch_offsets(self):
        config = MagicMock(spec=PillowConfig)
        checkpoint = config.get_instance.return_value.get_checkpoint.return_value
        checkpoint.timestamp = None
        checkpoint.sequence_format = "json"
        checkpoint.wrapped_sequence = {TopicPartition("missing", 0): 0}
        consumer = MagicMock()
        with self.assertRaisesRegex(ValueError, "Kafka topics unavailable: missing"):
            get_pillow_json(config, consumer, available_topics={"existing"})
        consumer.end_offsets.assert_not_called()

    @patch("pillowtop.utils.get_kafka_consumer")
    @patch("pillowtop.utils.get_all_pillow_configs", return_value=[])
    def test_no_configured_workers_returns_empty_list(self, configs, consumer):
        self.assertEqual(get_all_pillows_json(include_errors=True), [])


class SystemDiagnosticViewTests(SimpleTestCase):
    @patch("corehq.apps.hqadmin.views.system.get_all_pillows_json", side_effect=RuntimeError("private detail"))
    def test_broker_failure_returns_actionable_json_without_private_details(self, get_status):
        from django.test import RequestFactory
        from corehq.apps.hqadmin.views.system import system_ajax
        response = system_ajax.__wrapped__(RequestFactory().get("/", {"api": "pillowtop"}))
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Check Kafka connectivity", response.content)
        self.assertNotIn(b"private detail", response.content)

    @patch("corehq.apps.hqadmin.views.system.run_checks")
    def test_service_check_messages_are_html_escaped(self, run_checks):
        from django.test import RequestFactory
        from corehq.apps.hqadmin.views.system import check_services
        result = SimpleNamespace(exception=None, success=False, duration=0.01, msg="<script>bad</script>")
        run_checks.return_value = [("service", result)]
        response = check_services.__wrapped__(RequestFactory().get("/"))
        self.assertIn(b"&lt;script&gt;", response.content)
        self.assertNotIn(b"<script>", response.content)

    @patch("corehq.apps.domain.decorators.IS_CONTRACTOR.enabled", return_value=False)
    def test_non_admin_cannot_read_diagnostics(self, contractor):
        from django.test import RequestFactory
        from corehq.apps.hqadmin.views.system import check_services, system_ajax
        request = RequestFactory().get("/")
        request.user = SimpleNamespace(username="operator", is_superuser=False)
        for view in (check_services, system_ajax):
            response = view(request)
            self.assertEqual(response.status_code, 302)


class CeleryMonitoringTests(SimpleTestCase):
    @patch("corehq.apps.hqadmin.service_checks.Heartbeat")
    def test_missing_heartbeat_is_not_reported_as_a_confirmed_blockage(self, heartbeat):
        from django.test import override_settings
        from corehq.celery_monitoring.heartbeat import HeartbeatNeverRecorded
        from corehq.apps.hqadmin.service_checks import check_celery
        heartbeat.return_value.get_and_report_blockage_duration.side_effect = HeartbeatNeverRecorded()
        with override_settings(CELERY_HEARTBEAT_THRESHOLDS={"celery": 60}):
            result = check_celery()
        self.assertFalse(result.success)
        self.assertIn("No heartbeat recorded", result.msg)
        self.assertIn("Celery Beat", result.msg)
        self.assertNotIn("has been blocked", result.msg)
