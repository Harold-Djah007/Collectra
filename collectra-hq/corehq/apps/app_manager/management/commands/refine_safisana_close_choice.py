"""Make the staged drying-bed closing form safe when a worker chooses No."""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.stage_safisana_close_only import (
    FORM_NAME, NS, XMLNS, one,
)
from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID


def refine_source(source):
    root = etree.fromstring(source.encode('utf-8') if isinstance(source, str) else source)
    data = root.xpath('//x:model/x:instance/*', namespaces=NS)
    if (len(data) != 1 or etree.QName(data[0]).namespace != XMLNS
            or [etree.QName(child).localname for child in data[0]]
            != ['notice', 'confirm_close', 'reason']):
        raise ValueError('The reviewed closing form fields have changed')
    confirm = one(root, '//x:bind[@nodeset="/data/confirm_close"]')
    reason = one(root, '//x:bind[@nodeset="/data/reason"]')
    if (confirm.get('required') != 'true()' or confirm.get('constraint') != ". = 'yes'"
            or reason.get('required') != 'true()' or reason.get('relevant') is not None):
        raise ValueError('The reviewed closing form validation has changed')
    choices = root.xpath('//h:body/x:select1[@ref="/data/confirm_close"]/x:item/x:value/text()', namespaces=NS)
    if choices != ['yes', 'no']:
        raise ValueError('The closing form choices have changed')
    no_label = one(root, '//x:itext/x:translation[@lang="en"]/x:text[@id="close-label-4"]/x:value')
    if no_label.text != 'No, return to monitoring':
        raise ValueError('The reviewed No label has changed')
    confirm.attrib.pop('constraint')
    reason.set('relevant', "/data/confirm_close = 'yes'")
    no_label.text = 'No, keep this batch open'
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


def check_shared_blob_root():
    """Refuse writes to a worktree blob store the test server cannot read."""
    localsettings = Path.cwd() / 'localsettings.py'
    if localsettings.is_symlink():
        expected = (localsettings.resolve().parent / 'sharedfiles' / 'blobdb').resolve()
        actual = Path(settings.SHARED_DRIVE_CONF.blob_dir).resolve()
        if actual != expected:
            raise ValueError(
                f'Wrong blob root: {actual}. Export COLLECTRA_SHARED_DRIVE_ROOT='
                f'{expected.parent} and rerun before applying.')


class Command(BaseCommand):
    help = 'Preview or stage a safe No answer for the dedicated drying-bed closing form.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply, **options):
        try:
            app = get_app('safisana', APP_ID)
            matches = [(module, form) for module in app.get_modules()
                       for form in module.get_forms()
                       if form.default_name() == FORM_NAME and form.xmlns == XMLNS]
            if len(matches) != 1:
                raise ValueError('Expected exactly one dedicated closing form')
            module, form = matches[0]
            condition = form.actions.close_case.condition
            if (module.case_type != 'dryingbed' or form.requires != 'case'
                    or condition.type != 'always'):
                raise ValueError('The closing case action differs from the reviewed draft')
            source = form.source.encode('utf-8') if isinstance(form.source, str) else form.source
            refined = refine_source(source)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'drying-bed-close-safe-no-preview.xml'
            preview.write_bytes(refined)
            self.stdout.write(f'Preview: {preview}')
            if not apply:
                self.stdout.write('No application document was changed.')
                return
            check_shared_blob_root()
            digest = hashlib.sha256(source).hexdigest()[:12]
            backup = directory / f'{APP_ID}-{form.unique_id}-{digest}-before-safe-no.json'
            with backup.open('x', encoding='utf-8') as handle:
                json.dump({'source': source.decode('utf-8'), 'close_condition': condition.to_json()},
                          handle, ensure_ascii=False, indent=2)
            form.source = refined.decode('utf-8')
            condition.type = 'if'
            condition.question = '/data/confirm_close'
            condition.answer = 'yes'
            condition.operator = '='
            rendered = form.render_xform()
            etree.fromstring(rendered.encode('utf-8') if isinstance(rendered, str) else rendered)
            app.save()
            self.stdout.write('Saved editable closing form. No mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
