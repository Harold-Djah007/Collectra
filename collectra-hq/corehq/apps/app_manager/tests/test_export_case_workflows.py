"""Checks for the read-only app case-workflow exporter."""

import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.export_case_workflows import form_record


class ExportCaseWorkflowsTest(SimpleTestCase):
    def test_form_record_keeps_case_name_and_close_mapping(self):
        condition = SimpleNamespace(type='if', question='/data/close_batch', answer='yes', operator='=')
        opening = SimpleNamespace(
            condition=SimpleNamespace(type='always', question='', answer='', operator='='),
            name_update=SimpleNamespace(question_path='/data/list/drying_bed_batch_name'),
            external_id='',
        )
        updating = SimpleNamespace(
            condition=SimpleNamespace(type='never', question='', answer='', operator='='),
            name_update=SimpleNamespace(question_path=''),
            update={'bed_number': SimpleNamespace(question_path='/data/list/drying_bed_nmbr')},
        )
        form = SimpleNamespace(
            unique_id='form-id', default_name=lambda: 'Batch Registration',
            actions=SimpleNamespace(open_case=opening, update_case=updating,
                                    close_case=SimpleNamespace(condition=condition)),
            source='<data/>',
        )
        app = SimpleNamespace(_id='app-id', name='Processing - Plant')
        module = SimpleNamespace(unique_id='module-id', default_name=lambda: 'Drying Bed', case_type='bed')

        record = form_record(app, module, form, include_source=True)

        assert record['open_case']['name_question'] == '/data/list/drying_bed_batch_name'
        assert record['update_case']['properties']['bed_number'] == '/data/list/drying_bed_nmbr'
        assert record['close_case']['condition']['question'] == '/data/close_batch'
        assert record['xml'] == '<data/>'

    @patch('corehq.apps.app_manager.management.commands.export_case_workflows.get_apps_in_domain')
    def test_export_does_not_write_to_applications(self, get_apps):
        app = SimpleNamespace(_id='selected-app', get_modules=lambda: [], name='Processing - Plant')
        get_apps.return_value = [app]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'workflows.json'
            call_command('export_case_workflows', 'safisana', '--output', str(output),
                         '--app-id', 'selected-app')
            assert output.read_text() == '[]'
        get_apps.assert_called_once_with('safisana', include_remote=False)
