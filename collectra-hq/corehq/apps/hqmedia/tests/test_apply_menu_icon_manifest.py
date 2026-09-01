import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.management.base import CommandError
from PIL import Image

from corehq.apps.hqmedia.management.commands.apply_menu_icon_manifest import (
    MAX_ICON_DIMENSION,
    AuditMultimediaCommand,
    Command,
    load_and_validate_manifest,
    validate_app_reference,
)
from corehq.apps.hqmedia.models import CommCareImage


def png_bytes(size=(16, 16)):
    output = BytesIO()
    Image.new('RGBA', size, (12, 166, 154, 255)).save(output, format='PNG')
    return output.getvalue()


def write_manifest(tmp_path, **overrides):
    icon_path = tmp_path / 'icons' / 'menu.png'
    icon_path.parent.mkdir()
    icon_path.write_bytes(png_bytes())
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


def mutate_manifest(path, mutation):
    manifest = json.loads(path.read_text(encoding='utf-8'))
    mutation(manifest)
    path.write_text(json.dumps(manifest), encoding='utf-8')


class FakeApp:
    def __init__(self):
        self._id = 'app-id'
        self.name = 'App'
        self.multimedia_map = {}
        self.created_mappings = []
        self.save_count = 0
        self.reference = SimpleNamespace(
            path='jr://file/commcare/image/module0.png',
            is_menu_media=True,
            media_class=CommCareImage,
        )

    def all_media(self):
        return [self.reference]

    def create_mapping(self, media, target_path, save=False):
        self.created_mappings.append((media, target_path, save))

    def save(self):
        self.save_count += 1


def test_valid_manifest(tmp_path):
    _, _, mappings = load_and_validate_manifest(
        write_manifest(tmp_path), 'safisana'
    )

    assert len(mappings) == 1
    assert mappings[0]['icon_path'] == tmp_path / 'icons' / 'menu.png'


def test_rejects_non_object_manifest(tmp_path):
    path = tmp_path / 'manifest.json'
    path.write_text('[]', encoding='utf-8')

    with pytest.raises(CommandError, match='root must be an object'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_wrong_domain(tmp_path):
    with pytest.raises(CommandError, match='does not match'):
        load_and_validate_manifest(write_manifest(tmp_path), 'other-domain')


@pytest.mark.parametrize('mapping_count', [True, '1', None])
def test_rejects_non_integer_mapping_count(tmp_path, mapping_count):
    path = write_manifest(tmp_path, mapping_count=mapping_count)

    with pytest.raises(CommandError, match='must be an integer'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_mapping_count_mismatch(tmp_path):
    path = write_manifest(tmp_path, mapping_count=2)

    with pytest.raises(CommandError, match='mapping_count'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_duplicate_app_path(tmp_path):
    path = write_manifest(tmp_path)

    def duplicate_mapping(manifest):
        manifest['mappings'].append(dict(manifest['mappings'][0]))
        manifest['mapping_count'] = 2

    mutate_manifest(path, duplicate_mapping)

    with pytest.raises(CommandError, match='Duplicate app/path'):
        load_and_validate_manifest(path, 'safisana')


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('app_id', ''),
        ('app_name', None),
        ('item_name', 42),
        ('target_path', '   '),
        ('icon', []),
    ],
)
def test_rejects_invalid_mapping_text_fields(tmp_path, field, value):
    path = write_manifest(tmp_path)
    mutate_manifest(path, lambda manifest: manifest['mappings'][0].update({field: value}))

    with pytest.raises(CommandError, match='must be a non-empty string'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_unsupported_item_type(tmp_path):
    path = write_manifest(tmp_path)
    mutate_manifest(
        path,
        lambda manifest: manifest['mappings'][0].update(
            {'item_type': 'question'}
        ),
    )

    with pytest.raises(CommandError, match='unsupported item_type'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_non_commcare_image_path(tmp_path):
    path = write_manifest(tmp_path)
    mutate_manifest(
        path,
        lambda manifest: manifest['mappings'][0].update(
            {'target_path': 'jr://file/commcare/audio/module0.mp3'}
        ),
    )

    with pytest.raises(CommandError, match='not a CommCare image path'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_icon_outside_manifest_directory(tmp_path):
    pack_path = tmp_path / 'pack'
    pack_path.mkdir()
    path = write_manifest(pack_path)
    mutate_manifest(
        path,
        lambda manifest: manifest['mappings'][0].update(
            {'icon': '../outside.png'}
        ),
    )
    (tmp_path / 'outside.png').write_bytes(png_bytes())

    with pytest.raises(CommandError, match='escapes'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_invalid_png_content(tmp_path):
    path = write_manifest(tmp_path)
    (tmp_path / 'icons' / 'menu.png').write_bytes(b'not-a-png')

    with pytest.raises(CommandError, match='not a valid PNG'):
        load_and_validate_manifest(path, 'safisana')


def test_rejects_oversized_png_dimensions(tmp_path):
    path = write_manifest(tmp_path)
    (tmp_path / 'icons' / 'menu.png').write_bytes(
        png_bytes((MAX_ICON_DIMENSION + 1, 1))
    )

    with pytest.raises(CommandError, match='icon dimensions'):
        load_and_validate_manifest(path, 'safisana')


def test_validate_app_reference_accepts_menu_image():
    app = FakeApp()

    validate_app_reference(
        app,
        {'target_path': 'jr://file/commcare/image/module0.png'},
    )


def test_validate_app_reference_rejects_question_media():
    app = FakeApp()
    app.reference.is_menu_media = False

    with pytest.raises(CommandError, match='not exclusively a menu image'):
        validate_app_reference(
            app,
            {'target_path': 'jr://file/commcare/image/module0.png'},
        )


def test_dry_run_writes_report_without_changing_app(tmp_path):
    manifest = write_manifest(tmp_path)
    report = tmp_path / 'reports' / 'dry-run.json'
    app = FakeApp()

    with patch(
        'corehq.apps.hqmedia.management.commands.apply_menu_icon_manifest.'
        'get_apps_in_domain',
        return_value=[app],
    ):
        Command().handle(
            'safisana',
            str(manifest),
            apply=False,
            report=str(report),
        )

    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['mode'] == 'dry-run'
    assert result['planned_mappings'] == 1
    assert result['applied_mappings'] == 0
    assert app.created_mappings == []
    assert app.save_count == 0


def test_apply_changes_exact_mapping_and_saves_once(tmp_path):
    manifest = write_manifest(tmp_path)
    report = tmp_path / 'apply.json'
    app = FakeApp()
    media = SimpleNamespace(_id='media-id')

    with (
        patch(
            'corehq.apps.hqmedia.management.commands.apply_menu_icon_manifest.'
            'get_apps_in_domain',
            return_value=[app],
        ),
        patch.object(
            AuditMultimediaCommand,
            '_get_or_create_fallback_media',
            return_value=media,
        ),
    ):
        Command().handle(
            'safisana',
            str(manifest),
            apply=True,
            report=str(report),
        )

    result = json.loads(report.read_text(encoding='utf-8'))
    assert result['mode'] == 'apply'
    assert result['planned_mappings'] == 1
    assert result['applied_mappings'] == 1
    assert result['changes'][0]['new_multimedia_id'] == 'media-id'
    assert app.created_mappings == [
        (media, 'jr://file/commcare/image/module0.png', False)
    ]
    assert app.save_count == 1
