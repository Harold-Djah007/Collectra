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


if __name__ == '__main__':
    unittest.main()
