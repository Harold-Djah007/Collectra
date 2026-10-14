"""Exercise missing services and stale per-project backup detection."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "deploy/production/runtime-check.py"
spec = importlib.util.spec_from_file_location("runtime_monitor", SCRIPT)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class RuntimeMonitorTest(unittest.TestCase):
    def test_running_services_are_accepted(self):
        containers = [{"Service": "web", "State": "running", "Health": "healthy"},
                      {"Service": "celery", "State": "running", "Health": ""}]
        self.assertEqual(monitor.service_failures(["web", "celery"], containers), [])

    def test_missing_service_is_not_silently_accepted(self):
        self.assertEqual(monitor.service_failures(["web"], []), ["web: container missing"])

    def test_failed_replicas_are_detected(self):
        for state, health in [("exited", ""), ("restarting", ""), ("running", "unhealthy"), ("running", "starting")]:
            with self.subTest(state=state, health=health):
                containers = [{"Service": "web", "State": "running", "Health": "healthy"},
                              {"Service": "web", "State": state, "Health": health}]
                self.assertTrue(monitor.service_failures(["web"], containers))

    def make_manifest(self, root, domain, timestamp, name="SHA256SUMS"):
        directory = root / f"{domain}-20261014T000000Z"
        directory.mkdir(exist_ok=True)
        manifest = directory / name
        manifest.write_text("verified backup fixture")
        os.utime(manifest, (timestamp, timestamp))

    def test_fresh_backup_for_another_domain_cannot_mask_missing_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_manifest(root, "test-1", 100000)
            self.assertIsNone(monitor.backup_failure(root, "test-1", 26, now=100001))
            self.assertIsNotNone(monitor.backup_failure(root, "safisana", 26, now=100001))

    def test_stale_backup_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_manifest(root, "safisana", 1000)
            self.assertIn("overdue", monitor.backup_failure(root, "safisana", 26, now=100000))

    def test_incomplete_manifest_is_not_a_successful_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_manifest(root, "safisana", 100000, name="SHA256SUMS.tmp")
            self.assertIsNotNone(monitor.backup_failure(root, "safisana", 26, now=100001))

    def test_future_backup_timestamp_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_manifest(root, "safisana", 100000)
            self.assertIn("future", monitor.backup_failure(root, "safisana", 26, now=99000))

    def test_low_available_memory_is_reported(self):
        self.assertIsNotNone(monitor.memory_failure("MemTotal: 8000000 kB\nMemAvailable: 400000 kB\n"))
        self.assertIsNone(monitor.memory_failure("MemTotal: 8000000 kB\nMemAvailable: 2000000 kB\n"))

    def test_missing_memory_metrics_are_not_assumed_healthy(self):
        self.assertIsNotNone(monitor.memory_failure("MemTotal: 8000000 kB\n"))

    def test_worker_heartbeat_requires_a_real_pong(self):
        self.assertTrue(monitor.worker_responded({"worker": {"ok": "pong"}}))
        for replies in ({}, [], {"worker": {"error": "unavailable"}}, {"worker": "invalid"}):
            with self.subTest(replies=replies):
                self.assertFalse(monitor.worker_responded(replies))
