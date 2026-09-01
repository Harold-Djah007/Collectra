import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from corehq.apps.hqmedia.management.commands.export_menu_icon_inventory import (
    Command,
    build_inventory,
    localized_values,
)


def make_app(app_id, app_name):
    blank_form = SimpleNamespace(
        unique_id='form-blank',
        name={'en': 'Registration'},
        media_image={},
    )
    mapped_form = SimpleNamespace(
        unique_id='form-mapped',
        name={'en': 'Follow-up'},
        media_image={
            'en': 'jr://file/commcare/image/follow-up.png'
        },
    )
    module = SimpleNamespace(
        unique_id='module-id',
        name={'en': 'Households'},
        media_image=None,
        forms=[blank_form, mapped_form],
    )
    return SimpleNamespace(
        _id=app_id,
        name=app_name,
        langs=['en'],
        modules=[module],
    )


def test_localized_values_handles_empty_string_and_mapping():
    assert localized_values(None) == {}
    assert localized_values('Menu') == {'default': 'Menu'}
    assert localized_values({'en': '', 'fr': 'Menu'}) == {
        'en': '',
        'fr': 'Menu',
    }


def test_build_inventory_includes_blank_and_mapped_slots():
    apps = [
        make_app('z-app', 'Zulu'),
        make_app('a-app', 'Alpha'),
    ]

    with patch(
        'corehq.apps.hqmedia.management.commands.'
        'export_menu_icon_inventory.get_apps_in_domain',
        return_value=apps,
    ):
        result = build_inventory('safisana')

    assert result['application_count'] == 2
    assert result['module_count'] == 2
    assert result['form_count'] == 4
    assert [app['app_name'] for app in result['applications']] == [
        'Alpha',
        'Zulu',
    ]
    first_module = result['applications'][0]['modules'][0]
    assert first_module['media_image'] == {}
    assert first_module['forms'][0]['media_image'] == {}
    assert first_module['forms'][1]['media_image'] == {
        'en': 'jr://file/commcare/image/follow-up.png'
    }


def test_command_writes_complete_read_only_report():
    app = make_app('app-id', 'Field App')

    with TemporaryDirectory() as directory:
        report = Path(directory) / 'inventory.json'
        with patch(
            'corehq.apps.hqmedia.management.commands.'
            'export_menu_icon_inventory.get_apps_in_domain',
            return_value=[app],
        ):
            Command().handle('safisana', str(report))

        result = json.loads(report.read_text(encoding='utf-8'))

    assert result['domain'] == 'safisana'
    assert result['application_count'] == 1
    assert result['applications'][0]['app_id'] == 'app-id'
    assert result['applications'][0]['modules'][0]['forms'][0][
        'name'
    ] == {'en': 'Registration'}
