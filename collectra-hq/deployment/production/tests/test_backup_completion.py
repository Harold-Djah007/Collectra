"""Verify failed backups never publish a completion manifest."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[4] / "deploy/production/backup-domain.sh"
DOCKER_STUB = r"""
import io, os, sys, tarfile, zipfile
from pathlib import Path
args = sys.argv[1:]
if "pg_dumpall" in args:
    if os.environ.get("FAIL_DUMP"):
        sys.exit(2)
    print("-- disposable backup fixture")
else:
    root = Path(os.environ["COLLECTRA_BACKUP_DIR"]) / args[-1].split("/")[-1]
    if "dump_domain_data" in args:
        with zipfile.ZipFile(root / "data-dump-safisana-fixture.zip", "w") as archive:
            archive.writestr("fixture.json", "{}")
    elif "run_blob_export" in args:
        with tarfile.open(root / "fixture-safisana-blobs.tar.gz", "w:gz") as archive:
            data = b"fixture"
            item = tarfile.TarInfo("fixture.txt")
            item.size = len(data)
            archive.addfile(item, io.BytesIO(data))
"""


@unittest.skipUnless(os.name == "posix", "Requires native bash and archive tools")
class BackupCompletionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        shutil.copyfile(SCRIPT, self.root / "backup-domain.sh")
        self.backups = self.root / "backups"
        self.backups.mkdir()
        (self.root / ".env").write_text(f"COLLECTRA_BACKUP_DIR={self.backups}\n")
        binary = self.root / "bin"
        binary.mkdir()
        docker = binary / "docker"
        docker.write_text(f"#!{sys.executable}\n" + DOCKER_STUB)
        docker.chmod(0o700)
        date = binary / "date"
        date.write_text("#!/bin/sh\nprintf '20261014T000000Z\n'\n")
        date.chmod(0o700)
        checksum = binary / "sha256sum"
        checksum.write_text('#!/bin/sh\nif [ "$1" = "-c" ] && [ -n "$FAIL_CHECKSUM" ]; then exit 2; fi\nexec /usr/bin/sha256sum "$@"\n')
        checksum.chmod(0o700)
        self.env = {**os.environ, "PATH": f"{binary}:{os.environ['PATH']}"}

    def run_backup(self, **flags):
        return subprocess.run(["bash", str(self.root / "backup-domain.sh"), "safisana"],
                              capture_output=True, text=True, env={**self.env, **flags})

    def test_complete_archive_set_publishes_verified_manifest(self):
        result = self.run_backup()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.backups / "safisana-20261014T000000Z/SHA256SUMS"
        self.assertTrue(manifest.is_file())
        self.assertFalse(manifest.with_suffix(".tmp").exists())
        self.assertIn("postgres-all.sql.gz", manifest.read_text())

    def test_database_dump_failure_cannot_mark_backup_complete(self):
        result = self.run_backup(FAIL_DUMP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(list(self.backups.glob("*/SHA256SUMS")))

    def test_checksum_failure_cannot_mark_backup_complete(self):
        result = self.run_backup(FAIL_CHECKSUM="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(list(self.backups.glob("*/SHA256SUMS")))

    def test_same_timestamp_cannot_overwrite_previous_verified_backup(self):
        self.assertEqual(self.run_backup().returncode, 0)
        manifest = self.backups / "safisana-20261014T000000Z/SHA256SUMS"
        original = manifest.read_bytes()
        self.assertNotEqual(self.run_backup().returncode, 0)
        self.assertEqual(manifest.read_bytes(), original)
