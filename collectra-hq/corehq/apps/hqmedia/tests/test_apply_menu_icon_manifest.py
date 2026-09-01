import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from django.core.management.base import CommandError

from corehq.apps.hqmedia.management.commands.apply_menu_icon_manifest import (
    load_and_validate_manifest,
)


def write_manifest(tmp_path, **overrides):
    icon_path = tmp_path / 'icons' / 'menu.png'
    icon_path.parent.mkdir()
    icon_path.write_bytes(b'png')
    manifest = {
        'domain': 'safisana',
        'mapping_count': 1,
        'mappings': [
            {
                'app_id': 'app-id',
                'app_name': 'App',
                'item_type': 'module',
                'item_name': 'Menu',
                'target_path': 'jr://file/commcare/image/module0.png',
                'icon': 'icons/menu.png',
            }
        ],
    }
    manifest.update(overrides)
    path = tmp_path / 'manifest.json'
    path.write_text(json.dumps(manifest), encoding='utf-8')
    return path


def test_valid_manifest():
    with TemporaryDirectory() as directory:
        tmp_path = Path(directory)
        _, _, mappings = load_and_validate_manifest(
            write_manifest(tmp_path), 'safisana'
        )

        assert len(mappings) == 1
        assert mappings[0]['icon_path'] == tmp_path / 'icons' / 'menu.png'


def test_rejects_wrong_domain():
    with TemporaryDirectory() as directory:
        with pytest.raises(CommandError, match='does not match'):
            load_and_validate_manifest(
                write_manifest(Path(directory)), 'other-domain'
            )


def test_rejects_mapping_count_mismatch():
    with TemporaryDirectory() as directory:
        path = write_manifest(Path(directory), mapping_count=2)

        with pytest.raises(CommandError, match='mapping_count'):
            load_and_validate_manifest(path, 'safisana')


def test_rejects_duplicate_app_path():
    with TemporaryDirectory() as directory:
        path = write_manifest(Path(directory))
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['mappings'].append(dict(manifest['mappings'][0]))
        manifest['mapping_count'] = 2
        path.write_text(json.dumps(manifest), encoding='utf-8')

        with pytest.raises(CommandError, match='Duplicate app/path'):
            load_and_validate_manifest(path, 'safisana')


def test_rejects_icon_outside_manifest_directory():
    with TemporaryDirectory() as directory:
        tmp_path = Path(directory) / 'pack'
        tmp_path.mkdir()
        path = write_manifest(tmp_path)
        manifest = json.loads(path.read_text(encoding='utf-8'))
        manifest['mappings'][0]['icon'] = '../outside.png'
        Path(tmp_path.parent / 'outside.png').write_bytes(b'png')
        path.write_text(json.dumps(manifest), encoding='utf-8')

        with pytest.raises(CommandError, match='escapes'):
            load_and_validate_manifest(path, 'safisana')
