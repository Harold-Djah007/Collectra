"""Preview only: replace ambiguous yes/no checkboxes with single choices.

Positive choice values and every existing calculation are preserved. Force
closing and explicit acknowledgement controls are intentionally excluded.
"""

import json
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree


X = 'http://www.w3.org/2002/xforms'
H = 'http://www.w3.org/1999/xhtml'
NS = {'x': X, 'h': H}
# form id: (output name, {question path: optional (negative value, label)})
QUESTIONS = {
    'ade961bc9b3745b69d532301d3941720': (
        'ghana-oti-compost-registration', {
            '/data/naming/backdate_entry': ('today', "No, use today's date"),
        }),
    '0f99883b2c4e4aa287121086ef88fec3': (
        'incident-registration', {'/data/actions/first_aid_applied': None}),
    '8e7bd1a96fda46b7916f8e32394e3b9e': (
        'incident-follow-up', {
            '/data/do_you_intend_to_close_the_case': ('keep_open', 'No, keep this case open'),
            '/data/first_aid_replenished': None,
            '/data/happen_before': None,
        }),
    'b38c6397c7d34feea71a419bba619c6e': (
        'mixer-run-time', {'/data/mix_blade_sumberged': None}),
    'c04ab53c6c8546f4a51ba9dcc02fef18': (
        'planting', {'/data/planted': ('no', 'No, do not change to planted')}),
}


def one(root, expression):
    result = root.xpath(expression, namespaces=NS)
    if len(result) != 1:
        raise ValueError(f'Expected one match at {expression}, got {len(result)}')
    return result[0]


def improve_choice(root, path, negative):
    question = one(root, f'//h:body//x:select[@ref="{path}"]')
    items = question.xpath('./x:item', namespaces=NS)
    if len(items) != (1 if negative else 2):
        raise ValueError(f'Unexpected option count for {path}')
    original_values = [one(item, './x:value').text for item in items]
    if negative and negative[0] in original_values:
        raise ValueError(f'Negative option already exists for {path}')
    parent = question.getparent()
    at = list(parent).index(question)
    # Moving the original item elements retains their value tokens and itext
    # references, including the values used in case action conditions.
    question.tag = f'{{{X}}}select1'
    if negative:
        translation = one(root, '//x:model/x:itext/x:translation[@lang="en"]')
        identifier = 'choice-' + path.strip('/').replace('/', '-') + '-no-label'
        text = etree.SubElement(translation, f'{{{X}}}text', id=identifier)
        etree.SubElement(text, f'{{{X}}}value').text = negative[1]
        item = etree.SubElement(question, f'{{{X}}}item')
        etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('{identifier}')")
        etree.SubElement(item, f'{{{X}}}value').text = negative[0]
    # Some original selects have no question label: the former choice label
    # remains visible as the question prompt for clear yes/no questions.
    if not question.xpath('./x:label', namespaces=NS):
        first_label = one(items[0], './x:label')
        etree.SubElement(question, f'{{{X}}}label', ref=first_label.get('ref'))
    parent.remove(question)
    parent.insert(at, question)


def preview(export, output_dir):
    records = {r['form_id']: r for r in json.loads(Path(export).read_text(encoding='utf-8'))}
    files = []
    for form_id, (name, paths) in QUESTIONS.items():
        record = records[form_id]
        if not record.get('xml'):
            raise ValueError(f'{name} has no exported source XML')
        root = etree.parse(BytesIO(record['xml'].encode('utf-8'))).getroot()
        before = {b.get('nodeset'): dict(b.attrib) for b in root.xpath('//x:bind', namespaces=NS)}
        for path, negative in paths.items():
            improve_choice(root, path, negative)
        after = {b.get('nodeset'): dict(b.attrib) for b in root.xpath('//x:bind', namespaces=NS)}
        if before != after:
            raise ValueError(f'{name} changed an existing binding')
        xml = etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)
        etree.fromstring(xml)
        files.append((name, xml))
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    for name, xml in files:
        (directory / f'{name}-choice-preview.xml').write_bytes(xml)
    return directory


class Command(BaseCommand):
    help = 'Prepare local choice-question previews without changing live applications.'

    def add_arguments(self, parser):
        parser.add_argument('--workflow-export', required=True)
        parser.add_argument('--output-dir', required=True)

    def handle(self, workflow_export, output_dir, **options):
        try:
            directory = preview(workflow_export, output_dir)
        except (KeyError, OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Wrote review-only choice previews to {directory}')
