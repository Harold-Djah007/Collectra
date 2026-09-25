"""Stage an offline-capable worker request form without changing any cases."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app


APP_ID = '43599346df8b71c72052e07e42b241cd'
REGISTRATION_FORM_ID = '49bde2379a3a4ee888bcce8b1e690b2f'
REQUEST_XMLNS = 'http://openrosa.org/formdesigner/4F71598B-BE64-4BAF-8256-E340A490B673'
FORM_NAME = 'Request to reopen a drying-bed case'
X = 'http://www.w3.org/2002/xforms'
H = 'http://www.w3.org/1999/xhtml'
JR = 'http://openrosa.org/javarosa'
NS = {'x': X, 'h': H}


def build_request_form():
    root = etree.Element(f'{{{H}}}html', nsmap={'h': H, None: X, 'jr': JR,
                                               'xsd': 'http://www.w3.org/2001/XMLSchema'})
    head = etree.SubElement(root, f'{{{H}}}head')
    etree.SubElement(head, f'{{{H}}}title').text = FORM_NAME
    model = etree.SubElement(head, f'{{{X}}}model')
    instance = etree.SubElement(model, f'{{{X}}}instance')
    data = etree.SubElement(instance, f'{{{REQUEST_XMLNS}}}data', nsmap={None: REQUEST_XMLNS})
    data.set('name', FORM_NAME)
    data.set('uiVersion', '1')
    data.set('version', '1')
    for name in ('notice', 'bed_number', 'batch_start_date', 'existing_batch_name', 'reason'):
        etree.SubElement(data, f'{{{REQUEST_XMLNS}}}{name}')
        properties = {'nodeset': f'/data/{name}', 'type': 'xsd:string'}
        if name == 'batch_start_date':
            properties['type'] = 'xsd:date'
        if name in ('bed_number', 'reason'):
            properties['required'] = 'true()'
        etree.SubElement(model, f'{{{X}}}bind', **properties)

    body = etree.SubElement(root, f'{{{H}}}body')
    question = etree.SubElement(body, f'{{{X}}}trigger', ref='/data/notice')
    etree.SubElement(question, f'{{{X}}}label').text = (
        'This sends a request to a supervisor. It does not reopen a case automatically.')
    bed = etree.SubElement(body, f'{{{X}}}select1', ref='/data/bed_number')
    etree.SubElement(bed, f'{{{X}}}label').text = 'Which drying bed was closed by mistake?'
    for number in range(1, 7):
        choice = etree.SubElement(bed, f'{{{X}}}item')
        etree.SubElement(choice, f'{{{X}}}label').text = f'Drying bed {number}'
        etree.SubElement(choice, f'{{{X}}}value').text = f'dry_bed_{number}'
    choice = etree.SubElement(bed, f'{{{X}}}item')
    etree.SubElement(choice, f'{{{X}}}label').text = 'Other or unsure'
    etree.SubElement(choice, f'{{{X}}}value').text = 'other'
    for name, prompt in (
        ('batch_start_date', 'When did the batch start? Leave blank if unsure.'),
        ('existing_batch_name', 'Existing batch number, if known (optional)'),
        ('reason', 'Why should this case be reopened?'),
    ):
        question = etree.SubElement(body, f'{{{X}}}input', ref=f'/data/{name}')
        etree.SubElement(question, f'{{{X}}}label').text = prompt
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


class Command(BaseCommand):
    help = 'Preview or add an offline reopening request form to the editable Safisana app.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply, **options):
        try:
            app = get_app('safisana', APP_ID)
            module = next((module for module in app.get_modules()
                           if any(form.unique_id == REGISTRATION_FORM_ID
                                  for form in module.get_forms())), None)
            if module is None:
                raise ValueError('The reviewed drying-bed registration module was not found')
            if 'en' not in app.langs:
                raise ValueError('The reviewed English app language was not found')
            for form in module.get_forms():
                if form.default_name() == FORM_NAME or REQUEST_XMLNS in form.source:
                    raise ValueError('A reopening request form already exists in this module')
            xml = build_request_form()
            etree.fromstring(xml)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'drying-bed-reopen-request-preview.xml'
            preview.write_bytes(xml)
            self.stdout.write(f'Preview: {preview}')
            if not apply:
                self.stdout.write('No application document was changed.')
                return
            backup = directory / f'{APP_ID}-before-reopen-request.json'
            with backup.open('x', encoding='utf-8') as handle:
                json.dump(app.to_json(), handle, ensure_ascii=False, indent=2, default=str)
            app.new_form(module.id, FORM_NAME, 'en', attachment=xml.decode('utf-8'))
            app.save()
            self.stdout.write('Added an editable request form. No mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
