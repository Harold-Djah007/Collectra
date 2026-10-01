import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.management.base import CommandError
from django.test import SimpleTestCase

from corehq.apps.app_manager.management.commands.check_hq_form_readiness import Command


TARGET = 'corehq.apps.app_manager.management.commands.check_hq_form_readiness'
XML = b'''<h:html xmlns:h="http://www.w3.org/1999/xhtml" xmlns="http://www.w3.org/2002/xforms">
<h:head><model><instance><data xmlns="urn:test"/></instance></model></h:head><h:body/></h:html>'''


class TestFormReadinessCommand(SimpleTestCase):
    def app(self):
        form = SimpleNamespace(unique_id='form-id', default_name=lambda: 'Morning', form_type='module_form')
        app = Mock()
        app._id = 'app-id'
        app.name = 'Processing - Plant'
        app.get_modules.return_value = [SimpleNamespace(get_forms=lambda: [form])]
        app.fetch_attachment.return_value = XML
        return app

    def run_check(self, app, directory, validate=False):
        output = Path(directory) / 'readiness.json'
        with patch(TARGET + '.get_apps_in_domain', return_value=[app]):
            Command().handle(domain='safisana', app_ids=[], validate_xforms=validate, output=str(output))
        return json.loads(output.read_text())

    def test_direct_storage_read_and_no_saves(self):
        app = self.app()
        with TemporaryDirectory() as directory:
            report = self.run_check(app, directory)
        assert report['forms_with_problems'] == 0
        assert report['results'][0]['engine_validation'] == 'not_requested'
        app.fetch_attachment.assert_called_once_with('form-id.xml')
        app.lazy_fetch_attachment.assert_not_called()
        app.save.assert_not_called()

    def test_missing_blob_fails_and_leaves_a_report(self):
        app = self.app()
        app.fetch_attachment.side_effect = FileNotFoundError('Missing XML')
        with TemporaryDirectory() as directory:
            with self.assertRaises(CommandError):
                self.run_check(app, directory)
            report = json.loads((Path(directory) / 'readiness.json').read_text())
        assert report['forms_with_problems'] == 1
        assert 'Missing XML' in report['results'][0]['problems'][0]
        app.save.assert_not_called()

    def test_engine_failure_is_not_reported_as_passed(self):
        app = self.app()
        with TemporaryDirectory() as directory, patch(TARGET + '.XForm') as xform, \
                patch(TARGET + '.validate_xform', side_effect=ValueError('Invalid calculation')):
            from lxml import etree
            xform.return_value.xml = etree.fromstring(XML)
            with self.assertRaises(CommandError):
                self.run_check(app, directory, validate=True)
            report = json.loads((Path(directory) / 'readiness.json').read_text())
        assert report['results'][0]['engine_validation'] == 'failed'
        assert 'Invalid calculation' in report['results'][0]['problems'][0]

    def test_unknown_app_does_not_silently_pass(self):
        with patch(TARGET + '.get_apps_in_domain', return_value=[self.app()]):
            with self.assertRaises(CommandError):
                Command().handle('safisana', ['missing-app'], False, '/unused')

    def test_native_validator_is_called_without_using_form_validation_cache(self):
        app = self.app()
        with TemporaryDirectory() as directory, patch(TARGET + '.XForm') as xform, \
                patch(TARGET + '.validate_xform') as validate:
            from lxml import etree
            xform.return_value.xml = etree.fromstring(XML)
            report = self.run_check(app, directory, validate=True)
        assert report['results'][0]['engine_validation'] == 'passed'
        validate.assert_called_once()
        xform.return_value.strip_vellum_ns_attributes.assert_called_once()
        app.save.assert_not_called()
