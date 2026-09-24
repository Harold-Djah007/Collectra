"""Prepare read-only previews of explicit attention questions for two forms."""

import json
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree


FORM_IDS = {
    'morning-checks': 'f178cd42432c4069b14e27e6b8b042e2',
    'metering-round': '26a5eff6fc3a4c8ea779cb1edc0a1066',
}
X = 'http://www.w3.org/2002/xforms'
H = 'http://www.w3.org/1999/xhtml'
NS = {'x': X, 'h': H}
ISSUE_STATUSES = ('needs_attention', 'not_completed')


def one(element, expression):
    matches = element.xpath(expression, namespaces=NS)
    if len(matches) != 1:
        raise ValueError(f'Expected one element at {expression}, found {len(matches)}')
    return matches[0]


def add_text(translation, identifier, content):
    text = etree.SubElement(translation, f'{{{X}}}text', id=identifier)
    etree.SubElement(text, f'{{{X}}}value').text = content


def add_choice(body, path, identifier, choices):
    select = etree.SubElement(body, f'{{{X}}}select1', ref=path)
    etree.SubElement(select, f'{{{X}}}label', ref=f"jr:itext('{identifier}')")
    for value, text_id in choices:
        item = etree.SubElement(select, f'{{{X}}}item')
        etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('{text_id}')")
        etree.SubElement(item, f'{{{X}}}value').text = value


def upgrade_morning_checkboxes(root):
    """Keep the 12 legacy answer paths while collecting an unambiguous status."""
    model = one(root, '//x:model')
    data = one(model, './x:instance/*')
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    add_text(translation, 'status-completed-label', 'Completed and okay')
    add_text(translation, 'status-needs_attention-label', 'Needs attention')
    add_text(translation, 'status-not_completed-label', 'Not completed')
    add_text(translation, 'status-not_applicable-label', 'Not applicable today')
    status_paths = []
    checks = root.xpath('//h:body//x:select', namespaces=NS)
    if len(checks) != 12:
        raise ValueError('Expected the 12 reviewed Morning Checks checkboxes')
    for check in checks:
        path = check.get('ref')
        parts = path.split('/')
        choice = one(check, './x:item')
        value = one(choice, './x:value').text
        old_label = one(choice, './x:label').get('ref')
        status_path = '/'.join(parts[:-1] + [parts[-1] + '_status'])
        group_data = one(data, f'./*[local-name()="{parts[-2]}"]')
        etree.SubElement(group_data, f'{{{etree.QName(data).namespace}}}{parts[-1]}_status')
        original_bind = one(model, f'./x:bind[@nodeset="{path}"]')
        if original_bind.get('calculate') or choice.xpath('./x:value/text()', namespaces=NS) != [value]:
            raise ValueError(f'Original checkbox {path} has changed')
        # A checked legacy value means the worker performed the check, even if
        # the result now requires follow-up. Existing report fields remain.
        original_bind.set('calculate',
                          f"if({status_path} = 'completed' or {status_path} = 'needs_attention', "
                          f"'{value}', '')")
        model.insert(list(model).index(original_bind) + 1,
                     etree.Element(f'{{{X}}}bind', nodeset=status_path, required='true()'))
        parent = check.getparent()
        at = list(parent).index(check)
        parent.remove(check)
        replacement = etree.Element(f'{{{X}}}select1', ref=status_path)
        etree.SubElement(replacement, f'{{{X}}}label', ref=old_label)
        for status in ('completed', 'needs_attention', 'not_completed', 'not_applicable'):
            item = etree.SubElement(replacement, f'{{{X}}}item')
            etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('status-{status}-label')")
            etree.SubElement(item, f'{{{X}}}value').text = status
        parent.insert(at, replacement)
        status_paths.append(status_path)
    return status_paths


def upgrade_metering_round_type(root):
    """Use one choice for week/month, retaining both original export fields."""
    model = one(root, '//x:model')
    group = one(root, '//h:body/x:group[@ref="/data/week_month"]')
    trigger = one(group, './x:trigger[@ref="/data/week_month/type_of_round"]')
    week = one(group, './x:select[@ref="/data/week_month/week"]')
    month = one(group, './x:select[@ref="/data/week_month/month"]')
    for question, value in ((week, 'week'), (month, 'month')):
        if one(one(question, './x:item'), './x:value').text != value:
            raise ValueError(f'Unexpected {value} choice in Metering Round')
        bind = one(model, f'./x:bind[@nodeset="/data/week_month/{value}"]')
        if bind.get('calculate'):
            raise ValueError(f'Existing {value} calculation changed')
        bind.set('calculate',
                 f"if(/data/week_month/type_of_round = '{value}', '{value}', '')")
    one(model, './x:bind[@nodeset="/data/week_month/type_of_round"]').set('required', 'true()')
    at = list(group).index(trigger)
    group.remove(trigger)
    group.remove(week)
    group.remove(month)
    choice = etree.Element(f'{{{X}}}select1', ref='/data/week_month/type_of_round')
    etree.SubElement(choice, f'{{{X}}}label', ref="jr:itext('week_month/type_of_round-label')")
    for value in ('week', 'month'):
        item = etree.SubElement(choice, f'{{{X}}}item')
        etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('week_month/{value}-{value}-label')")
        etree.SubElement(item, f'{{{X}}}value').text = value
    group.insert(at, choice)
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    one(translation, './x:text[@id="week_month/type_of_round-label"]/x:value').text = (
        'Is this a weekly or monthly metering round?')


def add_attention_questions(root, form_name):
    model = one(root, '//x:model')
    data = one(model, './x:instance/*')
    body = one(root, '//h:body')
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    if root.xpath('//x:bind[@nodeset="/data/needs_attention"]', namespaces=NS):
        raise ValueError('This form already contains an attention question')
    status_paths = upgrade_morning_checkboxes(root) if form_name == 'Morning Checks Daily' else []
    if form_name == 'Metering Round':
        upgrade_metering_round_type(root)
    for field in ('needs_attention', 'attention_severity', 'attention_note'):
        etree.SubElement(data, f'{{{etree.QName(data).namespace}}}{field}')
    insert = list(model).index(one(model, './x:itext'))
    attention_bind = etree.Element(f'{{{X}}}bind', nodeset='/data/needs_attention')
    if status_paths:
        issues = ' or '.join(f"{path} = '{status}'"
                             for path in status_paths for status in ISSUE_STATUSES)
        attention_bind.set('calculate', f"if({issues}, 'yes', 'no')")
    else:
        attention_bind.set('required', 'true()')
    model.insert(insert, attention_bind)
    model.insert(insert + 1, etree.Element(f'{{{X}}}bind', nodeset='/data/attention_severity',
                                          relevant="/data/needs_attention = 'yes'", required='true()'))
    model.insert(insert + 2, etree.Element(f'{{{X}}}bind', nodeset='/data/attention_note',
                                          type='xsd:string', relevant="/data/needs_attention = 'yes'",
                                          required='true()'))
    add_text(translation, 'needs_attention-label',
             f'Does anything in this {form_name} need attention?')
    add_text(translation, 'needs_attention-no-label', 'No, everything checked is okay')
    add_text(translation, 'needs_attention-yes-label', 'Yes, report an issue to HQ')
    add_text(translation, 'attention_severity-label', 'How soon does this need attention?')
    add_text(translation, 'attention_severity-urgent-label', 'Urgent — act now')
    add_text(translation, 'attention_severity-follow_up-label', 'Follow up soon')
    add_text(translation, 'attention_note-label',
             'Describe the issue, equipment or meter, and what you observed.')
    if not status_paths:
        add_choice(body, '/data/needs_attention', 'needs_attention-label',
                   [('no', 'needs_attention-no-label'), ('yes', 'needs_attention-yes-label')])
    add_choice(body, '/data/attention_severity', 'attention_severity-label',
               [('urgent', 'attention_severity-urgent-label'),
                ('follow_up', 'attention_severity-follow_up-label')])
    note = etree.SubElement(body, f'{{{X}}}input', ref='/data/attention_note')
    etree.SubElement(note, f'{{{X}}}label', ref="jr:itext('attention_note-label')")


def preview(export, output_dir):
    records = {record['form_id']: record for record in json.loads(Path(export).read_text(encoding='utf-8'))}
    directory = Path(output_dir).expanduser()
    previews = []
    for name, form_id in FORM_IDS.items():
        record = records[form_id]
        if record['app_id'] != '43599346df8b71c72052e07e42b241cd' or not record.get('xml'):
            raise ValueError(f'{name} must have original XML from Processing - Plant')
        root = etree.parse(BytesIO(record['xml'].encode('utf-8'))).getroot()
        formulas = {b.get('nodeset'): b.get('calculate') for b in
                    root.xpath('//x:bind[@calculate]', namespaces=NS)}
        add_attention_questions(root, record['form_name'])
        if any(one(root, f'//x:bind[@nodeset="{path}"]').get('calculate') != formula
               for path, formula in formulas.items()):
            raise ValueError(f'{name} changed an existing calculation')
        xml = etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        etree.fromstring(xml)
        previews.append((name, xml))
    directory.mkdir(parents=True, exist_ok=True)
    for name, xml in previews:
        (directory / f'{name}-attention-preview.xml').write_bytes(xml)
    return directory


class Command(BaseCommand):
    help = 'Create local attention-question previews without editing the live forms.'

    def add_arguments(self, parser):
        parser.add_argument('--workflow-export', required=True)
        parser.add_argument('--output-dir', required=True)

    def handle(self, workflow_export, output_dir, **options):
        try:
            directory = preview(workflow_export, output_dir)
        except (OSError, ValueError, KeyError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Wrote review-only attention form XML to {directory}')
