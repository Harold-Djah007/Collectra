"""Exercise launcher failure paths with isolated command stubs."""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


class LauncherSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        self.env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "TEST_LOG": str(self.log),
            "XDG_STATE_HOME": str(self.root / "state"),
            "COLLECTRA_PROJECT_ROOT": str(ROOT / "collectra-hq"),
            "COLLECTRA_SKIP_ASSET_BUILD": "1",
            "COLLECTRA_LOCAL_HQ_LOG": str(self.root / "hq.log"),
            "COLLECTRA_HQ_READY_ATTEMPTS": "1",
        }

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f'#!/bin/bash\necho "{name} $*" >> "$TEST_LOG"\n{body}\n')
        path.chmod(0o755)

    def run_launcher(self, relative_path, *args):
        return subprocess.run(
            ["bash", str(ROOT / relative_path), *args],
            env=self.env, capture_output=True, text=True, timeout=10,
        )

    def commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_existing_proxy_survives_duplicate_launch(self):
        self.stub("docker", "exit 0")
        result = self.run_launcher(
            "deploy/local-testing/start-optimized-origin.sh", "collectra.example.com",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("already exists", result.stderr)
        self.assertNotIn("docker stop", self.commands())

    def test_occupied_origin_port_does_not_stop_other_container(self):
        self.stub("docker", '[[ "$1" == info ]]')
        self.stub("ss", "echo 'LISTEN 0 128 0.0.0.0:8000 0.0.0.0:*'")
        result = self.run_launcher(
            "deploy/local-testing/start-optimized-origin.sh", "collectra.example.com",
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Port 8000 is already in use", result.stderr)
        self.assertNotIn("docker stop", self.commands())

    def test_occupied_web_port_is_refused_without_killing_owner(self):
        self.stub("fuser", "exit 0")
        self.stub("docker", "exit 99")
        result = self.run_launcher("collectra-hq/local-bin/start-collectra")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already in use", result.stderr)
        self.assertNotIn("fuser -k", self.commands())
        self.assertNotIn("docker", self.commands())

    def test_duplicate_launcher_preserves_worker_pid_files(self):
        import fcntl

        state = self.root / "state" / "collectra"
        state.mkdir(parents=True)
        pid_file = state / "celery.pid"
        pid_file.write_text("12345\n")
        with (state / "launcher.lock").open("w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_launcher("collectra-hq/local-bin/start-collectra")
        self.assertEqual(result.returncode, 1)
        self.assertIn("already running", result.stderr)
        self.assertEqual(pid_file.read_text(), "12345\n")

    def test_termination_stops_only_owned_proxy(self):
        # Build an isolated repo so the HQ child never starts real services.
        script_dir = self.root / "deploy" / "local-testing"
        script_dir.mkdir(parents=True)
        source = ROOT / "deploy/local-testing/start-optimized-origin.sh"
        target = script_dir / source.name
        shutil.copyfile(source, target)
        launcher = self.root / "collectra-hq" / "local-bin" / "start-collectra"
        launcher.parent.mkdir(parents=True)
        launcher.write_text('#!/bin/bash\ntrap "exit 0" TERM\nwhile true; do sleep 0.1; done\n')
        launcher.chmod(0o755)
        self.stub("uv", "exit 0")
        self.stub("ss", "exit 0")
        self.stub("curl", "exit 0")
        self.stub("docker", '''
case "$1" in
    info|stop) exit 0 ;;
    container) exit 1 ;;
    run)
        while [[ "$1" != --cidfile ]]; do shift; done
        echo owned-container-id > "$2"
        kill -TERM "$PPID"
        exit 0 ;;
esac''')
        result = subprocess.run(
            ["bash", str(target), "collectra.example.com"],
            env=self.env, capture_output=True, text=True, timeout=10,
        )
        self.assertEqual(result.returncode, 143)
        self.assertIn("docker stop owned-container-id", self.commands())
        self.assertNotIn("docker stop collectra-local-accelerator", self.commands())


if __name__ == "__main__":
    unittest.main()
