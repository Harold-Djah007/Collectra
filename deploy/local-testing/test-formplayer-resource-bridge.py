"""Check resource bridge command construction without requiring Docker."""

import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest


class ResourceBridgeTests(unittest.TestCase):
    def run_bridge(self, port, hosts='172.17.0.1 host.docker.internal'):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            docker = root / 'docker'
            docker.write_text('''#!/usr/bin/env bash
printf '%s\\n' "$*" >> "$CALL_LOG"
if [[ $1 == exec ]]; then printf '%s\\n' "$HOSTS"; fi
''')
            docker.chmod(0o755)
            log = root / 'calls'
            environment = dict(os.environ, PATH=f'{directory}:{os.environ["PATH"]}',
                               CALL_LOG=str(log), HOSTS=hosts)
            script = Path(__file__).with_name('start-formplayer-resource-bridge.sh')
            result = subprocess.run(['bash', str(script), 'test-formplayer', port],
                                    env=environment, capture_output=True, text=True)
            calls = log.read_text() if log.exists() else ''
            return result, calls

    def test_routes_each_available_proxy_port_without_publishing(self):
        for port in range(8012, 8020):
            with self.subTest(port=port):
                result, calls = self.run_bridge(str(port))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--network container:test-formplayer', calls)
                self.assertIn(f'--from http://:{port} --to http://172.17.0.1:8011', calls)
                self.assertNotIn('--publish', calls)

    def test_invalid_port_does_not_start_container(self):
        result, calls = self.run_bridge('8080')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, '')

    def test_missing_host_mapping_does_not_start_container(self):
        result, calls = self.run_bridge('8012', hosts='127.0.0.1 localhost')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn('run --rm', calls)
        self.assertIn('host-gateway mapping', result.stderr)

    def test_readiness_accepts_redirect_without_following_it(self):
        self.check_readiness('HTTP/1.1 302 Found', expected=0)

    def test_readiness_accepts_success(self):
        self.check_readiness('HTTP/1.1 200 OK', expected=0)

    def test_readiness_rejects_bad_gateway_and_empty_response(self):
        for status in ['HTTP/1.1 502 Bad Gateway', '']:
            with self.subTest(status=status):
                self.check_readiness(status, expected=1)

    def check_readiness(self, status, expected):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            # Execute the actual in-container probe shell, replacing only nc.
            docker = root / 'docker'
            docker.write_text('#!/bin/sh\nshift 2\nexec "$@"\n')
            docker.chmod(0o755)
            nc = root / 'nc'
            nc.write_text('''#!/bin/sh
cat > "$REQUEST_LOG"
printf '%s\\r\\nLocation: https://unreachable.invalid/login\\r\\n\\r\\n' "$STATUS"
''')
            nc.chmod(0o755)
            request_log = root / 'request'
            environment = dict(os.environ, PATH=f'{directory}:{os.environ["PATH"]}',
                               REQUEST_LOG=str(request_log), STATUS=status)
            script = Path(__file__).with_name('check-formplayer-resource-bridge.sh')
            result = subprocess.run(['bash', str(script), 'test-bridge', '8012'],
                                    env=environment, capture_output=True, text=True, timeout=5)
            self.assertEqual(result.returncode, expected, result.stderr)
            self.assertIn('Host: localhost:8012', request_log.read_text())
            self.assertIn('GET /a/safisana/ HTTP/1.0', request_log.read_text())


if __name__ == '__main__':
    unittest.main()
