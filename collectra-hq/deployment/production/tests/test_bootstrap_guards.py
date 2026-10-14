"""Reject unsafe production settings before any container operation."""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "deploy/production/bootstrap.sh"


@unittest.skipUnless(os.name == "posix", "Requires native bash")
class BootstrapGuardTest(unittest.TestCase):
    def run_bootstrap(self, changes):
        settings = {"COLLECTRA_HOST": "collectra.example.com", "COLLECTRA_BACKUP_DIR": "/unused-backup-test",
                    "DJANGO_SECRET_KEY": "a" * 32, "POSTGRES_PASSWORD": "b" * 32,
                    "COUCHDB_PASSWORD": "c" * 32, "MINIO_ROOT_PASSWORD": "d" * 32,
                    "FORMPLAYER_AUTH_KEY": "e" * 32}
        settings.update(changes)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copyfile(SCRIPT, root / "bootstrap.sh")
            (root / ".env").write_text("\n".join(f"{k}={v}" for k, v in settings.items()) + "\n")
            binary = root / "bin"
            binary.mkdir()
            for command in ("docker", "curl"):
                stub = binary / command
                stub.write_text(f"#!/bin/sh\ntouch '{root / 'unexpected-container-operation'}'\nexit 99\n")
                stub.chmod(0o700)
            result = subprocess.run(["bash", str(root / "bootstrap.sh")], capture_output=True, text=True,
                                    env={**os.environ, "PATH": f"{binary}:{os.environ['PATH']}"})
            self.assertFalse((root / "unexpected-container-operation").exists())
            self.assertNotEqual(result.returncode, 0)
            for key in ("DJANGO_SECRET_KEY", "POSTGRES_PASSWORD", "COUCHDB_PASSWORD", "MINIO_ROOT_PASSWORD", "FORMPLAYER_AUTH_KEY"):
                self.assertNotIn(settings[key], result.stdout + result.stderr)
            return result.stdout

    def test_reused_service_secret_is_blocked(self):
        self.assertIn("must not reuse", self.run_bootstrap({"POSTGRES_PASSWORD": "a" * 32}))

    def test_placeholder_secret_is_blocked(self):
        self.assertIn("must be replaced", self.run_bootstrap({"POSTGRES_PASSWORD": "replace-with-a-postgres-password"}))

    def test_invalid_worker_counts_are_blocked(self):
        for name in ("COLLECTRA_WEB_WORKERS", "COLLECTRA_CELERY_CONCURRENCY"):
            for value in ("0", "-1", "abc"):
                with self.subTest(name=name, value=value):
                    self.assertIn("must be a positive integer", self.run_bootstrap({name: value}))
