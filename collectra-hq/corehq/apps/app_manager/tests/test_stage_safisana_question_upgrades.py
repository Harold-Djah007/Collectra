import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

from django.core.management.base import CommandError

from corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades import Command


class StageSafisanaQuestionUpgradesTest(TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / 'one.xml').write_bytes(b'<updated-one/>')
        (self.directory / 'two.xml').write_bytes(b'<updated-two/>')
        self.export = self.directory / 'export.json'
        self.export.write_text(json.dumps([
            {'form_id': 'one', 'app_id': 'app', 'xml': '<original-one/>'},
            {'form_id': 'two', 'app_id': 'app', 'xml': '<original-two/>'},
        ]))
        self.forms = {
            'one': Mock(source='<original-one/>'),
            'two': Mock(source='<original-two/>'),
        }
        self.app = Mock(_id='app', name='Safisana')
        self.app.get_form.side_effect = self.forms.__getitem__

    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.upgrades',
           return_value={'one': 'one.xml', 'two': 'two.xml'})
    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.get_app')
    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.save_xform')
    def test_dry_run_and_apply_save_app_once_after_both_forms(self, save_xform, get_app, upgrades):
        get_app.return_value = self.app
        options = dict(workflow_export=str(self.export), output_dir=str(self.directory))
        Command().handle(apply=False, **options)
        self.app.save.assert_not_called()
        save_xform.assert_not_called()

        Command().handle(apply=True, **options)
        self.assertEqual(save_xform.call_count, 2)
        self.app.save.assert_called_once_with()
        self.assertEqual((self.directory / 'original-xml-backups/app-one.xml').read_text(),
                         '<original-one/>')

    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.upgrades',
           return_value={'one': 'one.xml', 'two': 'two.xml'})
    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.get_app')
    @patch('corehq.apps.app_manager.management.commands.stage_safisana_question_upgrades.save_xform')
    def test_stale_export_stops_before_any_changes(self, save_xform, get_app, upgrades):
        get_app.return_value = self.app
        self.forms['two'].source = '<someone-else-edited/>'
        with self.assertRaisesRegex(CommandError, 'differs from the export'):
            Command().handle(workflow_export=str(self.export), output_dir=str(self.directory), apply=True)
        save_xform.assert_not_called()
        self.app.save.assert_not_called()
        self.assertFalse((self.directory / 'original-xml-backups').exists())
