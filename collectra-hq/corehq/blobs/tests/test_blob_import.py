import tarfile
import time
from io import BytesIO
from tempfile import NamedTemporaryFile
from timeit import Timer

from django.test import SimpleTestCase

from unittest.mock import patch

from corehq.blobs.management.commands.run_blob_import import (
    NUM_WORKERS,
    import_blobs_from_tgz,
)


class SleeperBlobDB:
    def copy_blob(self, content, key):
        # time.sleep() is not a coroutine. Worker must run in a separate
        # thread to run concurrently.
        time.sleep(0.1)


class ErrorBlobDB:
    def copy_blob(self, content, key):
        raise Exception('boom')


def import_sleep():
    with patch('corehq.blobs.management.commands.run_blob_import.get_blob_db') as mock_, \
            NamedTemporaryFile() as tempfile:
        mock_.return_value = SleeperBlobDB()
        make_blob_export(tempfile.name)
        results = import_blobs_from_tgz(tempfile.name)
        assert len(results) == NUM_WORKERS


def make_blob_export(filename):
    with tarfile.open(filename, 'w:gz') as tgzfile:
        for i in range(NUM_WORKERS):
            tarinfo = tarfile.TarInfo(name=f'key-{i}')
            tarinfo.size = len(b'spam')
            fileobj = BytesIO(b'spam')
            tgzfile.addfile(tarinfo, fileobj)


class BlobImportTests(SimpleTestCase):

    def test_all_blob_bytes_are_copied_once(self):
        copied = {}

        class RecordingBlobDB:
            def copy_blob(self, content, key):
                assert key not in copied
                copied[key] = content.read()

        with NamedTemporaryFile() as tempfile:
            make_blob_export(tempfile.name)
            with patch('corehq.blobs.management.commands.run_blob_import.get_blob_db', return_value=RecordingBlobDB()):
                import_blobs_from_tgz(tempfile.name)
        assert copied == {f'key-{i}': b'spam' for i in range(NUM_WORKERS)}

    def test_archive_members_are_not_cached(self):
        original_open = tarfile.open
        opened = []

        def tracked_open(*args, **kwargs):
            archive = original_open(*args, **kwargs)
            if kwargs.get('stream'):
                opened.append(archive)
            return archive

        with NamedTemporaryFile(suffix=" with spaces.tar.gz") as tempfile:
            make_blob_export(tempfile.name)
            with patch('corehq.blobs.management.commands.run_blob_import.tarfile.open', tracked_open), \
                    patch('corehq.blobs.management.commands.run_blob_import.get_blob_db', return_value=SleeperBlobDB()):
                import_blobs_from_tgz(tempfile.name)

        assert len(opened) == NUM_WORKERS + 1
        assert all(not archive.members for archive in opened)

    def test_concurrency(self):
        duration = Timer(
            'import_sleep()',
            setup="from corehq.blobs.tests.test_blob_import import import_sleep",
        ).timeit(1)
        # 5 workers each sleeping 0.1s should take less than 0.5s
        self.assertLess(duration, 0.1 * NUM_WORKERS)

    def test_errors(self):
        with patch('corehq.blobs.management.commands.run_blob_import.get_blob_db') as mock_, \
                NamedTemporaryFile() as tempfile:
            mock_.return_value = ErrorBlobDB()
            make_blob_export(tempfile.name)
            with self.assertRaisesRegex(Exception, 'boom'):
                import_blobs_from_tgz(tempfile.name)
