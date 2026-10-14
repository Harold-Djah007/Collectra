import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HQ = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


writer = load('build_writer', HQ / 'deployment/production/write_build_metadata.py')
gitinfo = load('build_gitinfo', HQ / 'corehq/ex-submodules/dimagi/utils/gitinfo.py')


class BuildMetadataTests(unittest.TestCase):
    def test_snapshot_works_without_git_history_and_is_stable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'app.py').write_text('version = 1')
            expected = writer.write_metadata(root)
            assert gitinfo.get_project_snapshot(directory) == expected
            assert writer.write_metadata(root) == expected
            (root / 'app.py').write_text('version = 2')
            assert writer.write_metadata(root) != expected

    def test_build_caches_do_not_change_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = writer.write_metadata(root)
            (root / 'node_modules').mkdir()
            (root / 'node_modules/cache.js').write_text('irrelevant')
            assert writer.write_metadata(root) == expected

    def test_invalid_fingerprint_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.collectra-build.json').write_text(json.dumps({'commits': [{'sha': 'invalid'}]}))
            with self.assertRaises(ValueError):
                gitinfo.get_project_snapshot(directory)
