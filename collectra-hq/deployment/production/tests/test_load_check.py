"""Verify latency sampling counts HTTP failures instead of reporting success."""
import importlib.util
import io
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[4] / "deploy/production/load-check.py"
spec = importlib.util.spec_from_file_location("load_check", SCRIPT)
load_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(load_check)


class LoadCheckTest(unittest.TestCase):
    def test_p95_uses_nearest_rank(self):
        self.assertEqual(load_check.percentile(list(range(1, 101)), .95), 95)
        self.assertEqual(load_check.percentile([200], .95), 200)

    def test_http_errors_are_counted(self):
        error = urllib.error.HTTPError("http://localhost/accounts/login/", 503, "Unavailable", {}, io.BytesIO())
        with patch.object(load_check.urllib.request, "urlopen", side_effect=error):
            status, latency = load_check.fetch("http://localhost/accounts/login/")
        self.assertEqual(status, 503)
        self.assertGreaterEqual(latency, 0)

    def test_connection_failure_is_counted(self):
        with patch.object(load_check.urllib.request, "urlopen", side_effect=urllib.error.URLError("refused")):
            self.assertEqual(load_check.fetch("http://localhost/accounts/login/")[0], 0)
