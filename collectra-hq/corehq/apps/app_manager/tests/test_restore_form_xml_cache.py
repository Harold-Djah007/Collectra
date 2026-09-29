"""Recovery commands must inspect blob storage despite stale lazy cache entries."""

import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from couchdbkit import ResourceNotFound
from django.core.management.base import CommandError

from hqscripts.management.commands.restore_app_form_xml import Command as RestoreOne
from hqscripts.management.commands.restore_missing_app_form_xmls import Command as RestoreMissing


def readable_app():
    form = SimpleNamespace(unique_id='form-id', default_name=lambda: 'Morning Checks')
    module = SimpleNamespace(get_forms=lambda: [form])
    app = Mock(name='app')
    app.name = 'Processing - Plant'
    app.get_modules.return_value = [module]
    app.fetch_attachment.return_value = b'<data/>'
    app.lazy_fetch_attachment.side_effect = ResourceNotFound('cached missing XML')
    return app


def test_batch_restore_ignores_cached_missing_result(tmp_path):
    app = readable_app()
    path = tmp_path / 'recovery.json'
    path.write_text(json.dumps({
        'domain': 'safisana', 'app_id': 'app-id',
        'forms': [{'form_id': 'form-id', 'xml': '<data>older XML</data>'}],
    }))
    with patch('hqscripts.management.commands.restore_missing_app_form_xmls.get_app', return_value=app):
        RestoreMissing().handle(str(path), dry_run=False)
    app.fetch_attachment.assert_called_once_with('form-id.xml')
    app.lazy_fetch_attachment.assert_not_called()
    app.lazy_put_attachment.assert_not_called()
    app.save.assert_not_called()


def test_single_restore_refuses_to_overwrite_when_only_lazy_cache_is_missing(tmp_path):
    app = readable_app()
    path = tmp_path / 'older.xml'
    path.write_text('<data>older XML</data>')
    with patch('hqscripts.management.commands.restore_app_form_xml.get_app', return_value=app):
        with pytest.raises(CommandError, match='already readable'):
            RestoreOne().handle('safisana', 'app-id', 'form-id', str(path))
    app.fetch_attachment.assert_called_once_with('form-id.xml')
    app.lazy_fetch_attachment.assert_not_called()
    app.lazy_put_attachment.assert_not_called()
    app.save.assert_not_called()
