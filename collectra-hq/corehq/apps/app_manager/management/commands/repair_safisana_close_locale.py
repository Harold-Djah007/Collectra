"""Repair the staged drying-bed closing form's missing Formplayer locale."""

import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.stage_safisana_close_only import (
    FORM_NAME, NS, XMLNS, add_english_localizer,
)
from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID


def repair_source(source):
    root = etree.fromstring(source.encode('utf-8') if isinstance(source, str) else source)
    if root.xpath('//x:model/x:itext', namespaces=NS):
        raise ValueError('The closing form already has translations; no repair is needed')
    data = root.xpath('//x:model/x:instance/*', namespaces=NS)
    if (len(data) != 1 or etree.QName(data[0]).namespace != XMLNS
            or [etree.QName(child).localname for child in data[0]]
            != ['notice', 'confirm_close', 'reason']):
        raise ValueError('The closing form fields have changed; review it manually')
    confirmation = root.xpath('//x:bind[@nodeset="/data/confirm_close"]', namespaces=NS)
    if len(confirmation) != 1 or confirmation[0].get('constraint') != ". = 'yes'":
        raise ValueError('The closing confirmation has changed; review it manually')
    labels = root.xpath('//h:body//x:label/text()', namespaces=NS)
    if labels != [
        'Save all final drying-bed measurements in Drying Bed monitoring before closing this case.',
        'Is this batch ready to close?', 'Yes, close this batch',
        'No, return to monitoring', 'Reason for closing this batch',
    ]:
        raise ValueError('The closing form labels have changed; review it manually')
    add_english_localizer(root)
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


class Command(BaseCommand):
    help = 'Preview or fix the staged Safisana closing form locale; no mobile build is released.'

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
                raise ValueError('Expected exactly one staged drying-bed closing form')
            module, form = matches[0]
            if (module.case_type != 'dryingbed' or form.requires != 'case'
                    or form.actions.close_case.condition.type != 'always'):
                raise ValueError('The closing form case action has changed; review it manually')
            original = form.source.encode('utf-8') if isinstance(form.source, str) else form.source
            repaired = repair_source(original)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'drying-bed-close-localized-preview.xml'
            preview.write_bytes(repaired)
            self.stdout.write(f'Preview: {preview}')
            if not apply:
                self.stdout.write('No application document was changed.')
                return
            digest = hashlib.sha256(original).hexdigest()[:12]
            backup = directory / f'{APP_ID}-{form.unique_id}-{digest}-before-locale.xml'
            with backup.open('xb') as handle:
                handle.write(original)
            form.source = repaired.decode('utf-8')
            rendered = form.render_xform()
            etree.fromstring(rendered.encode('utf-8') if isinstance(rendered, str) else rendered)
            app.save()
            self.stdout.write('Saved editable closing form with English locale; no mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
