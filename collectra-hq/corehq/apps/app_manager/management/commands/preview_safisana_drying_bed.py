"""Generate local XForm previews from a read-only Safisana workflow export.

This command does not write application documents or change existing cases.
Review and pilot the XML before publishing a new application version.
"""

import json
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree


FORM_IDS = {
    'registration': '49bde2379a3a4ee888bcce8b1e690b2f',
    'monitoring': '619d8e801fa14153aaa90165f7aadfd3',
}
X = 'http://www.w3.org/2002/xforms'
V = 'http://commcarehq.org/xforms/vellum'
JR = 'http://openrosa.org/javarosa'
NS = {'x': X, 'h': 'http://www.w3.org/1999/xhtml'}


def one(element, expression):
    matches = element.xpath(expression, namespaces=NS)
    if len(matches) != 1:
        raise ValueError(f'Expected one match for {expression}, found {len(matches)}')
    return matches[0]


def label(translation, identifier, value):
    text = etree.SubElement(translation, f'{{{X}}}text', id=identifier)
    etree.SubElement(text, f'{{{X}}}value').text = value


def select(group, path, label_id, choices, position=None):
    question = etree.Element(f'{{{X}}}select1', ref=path)
    etree.SubElement(question, f'{{{X}}}label', ref=f"jr:itext('{label_id}')")
    for value, text_id in choices:
        item = etree.SubElement(question, f'{{{X}}}item')
        etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('{text_id}')")
        etree.SubElement(item, f'{{{X}}}value').text = value
    if position is None:
        group.append(question)
    else:
        group.insert(position, question)
    return question


def change_registration(root):
    data = one(root, '//x:model/x:instance/*')
    lst = one(data, './*[local-name()="list"]')
    model = one(root, '//x:model')
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    group = one(root, '//h:body/x:group[@ref="/data/list"]')
    old = one(group, './x:input[@ref="/data/list/drying_bed_batch_name"]')
    bed = one(group, './x:select1[@ref="/data/list/drying_bed_nmbr"]')
    name_bind = one(model, './x:bind[@nodeset="/data/list/drying_bed_batch_name"]')
    if name_bind.get('type') != 'xsd:int' or name_bind.get('calculate'):
        raise ValueError('Existing batch-name type or calculation is unexpected')
    if [item.text for item in bed.xpath('./x:item/x:value', namespaces=NS)] != [
            'dry_bed_1', 'dry_bed_2', 'dry_bed_3', 'dry_bed_4', 'dry_bed_5', 'dry_bed_6', 'other']:
        raise ValueError('Existing drying-bed choice values have changed')

    lst.insert(0, etree.Element(f'{{{lst.nsmap[None]}}}registration_date'))
    etree.SubElement(lst, f'{{{lst.nsmap[None]}}}batch_on_bed_today')
    etree.SubElement(lst, f'{{{lst.nsmap[None]}}}manual_batch_name')
    before_name = list(model).index(name_bind)
    bind = etree.Element(f'{{{X}}}bind', nodeset='/data/list/registration_date',
                         type='xsd:date', required='true()', constraint='. <= today()')
    bind.set(f'{{{JR}}}constraintMsg', "jr:itext('registration_date-constraintMsg')")
    model.insert(before_name, bind)
    suffix = "if(/data/list/batch_on_bed_today = '1', '', /data/list/batch_on_bed_today)"
    bed_code = "'06'"
    for number in range(5, 0, -1):
        bed_code = f"if(/data/list/drying_bed_nmbr = 'dry_bed_{number}', '0{number}', {bed_code})"
    result = ("if(/data/list/drying_bed_nmbr = 'other', /data/list/manual_batch_name, "
              "if(/data/list/registration_date != '' and /data/list/drying_bed_nmbr != '' "
              "and /data/list/batch_on_bed_today != '', "
              f"int(concat(format-date(/data/list/registration_date, '%y%m%d'), {bed_code}, {suffix})), ''))")
    name_bind.set('calculate', result)
    name_bind.set('readonly', 'true()')
    name_bind.set('required', 'true()')
    after_bed = list(model).index(one(model, './x:bind[@nodeset="/data/list/drying_bed_nmbr"]')) + 1
    model.insert(after_bed, etree.Element(f'{{{X}}}bind', nodeset='/data/list/batch_on_bed_today',
                                      relevant="/data/list/drying_bed_nmbr != 'other'",
                                      required='true()'))
    model.insert(after_bed + 1, etree.Element(f'{{{X}}}bind', nodeset='/data/list/manual_batch_name',
                                          type='xsd:int', relevant="/data/list/drying_bed_nmbr = 'other'",
                                          required='true()', constraint='. > 0'))
    one(model, './x:bind[@nodeset="/data/list/drying_bed_nmbr"]').set('required', 'true()')
    itext = one(translation, './x:text[@id="list/drying_bed_batch_name-label"]/x:value')
    itext.text = 'Batch number (generated from date, bed and batch order)'
    one(translation, './x:text[@id="list/drying_bed_nmbr-label"]/x:value').text = 'Which drying bed?'
    label(translation, 'list/registration_date-label', 'Date this batch started (today is preselected)')
    label(translation, 'registration_date-constraintMsg', 'Choose today or an earlier date.')
    label(translation, 'list/batch_on_bed_today-label',
          'Which batch on this bed today? Check the current case list before opening another.')
    for number, word in ((1, 'First'), (2, 'Second'), (3, 'Third')):
        label(translation, f'list/batch_on_bed_today-{number}-label', f'{word} batch')
    label(translation, 'list/manual_batch_name-label', 'Other bed: enter the existing batch number')

    group.insert(0, etree.Element(f'{{{X}}}input', ref='/data/list/registration_date'))
    etree.SubElement(group[0], f'{{{X}}}label', ref="jr:itext('list/registration_date-label')")
    select(group, '/data/list/batch_on_bed_today', 'list/batch_on_bed_today-label',
           [(str(i), f'list/batch_on_bed_today-{i}-label') for i in range(1, 4)],
           list(group).index(bed) + 1)
    manual = etree.Element(f'{{{X}}}input', ref='/data/list/manual_batch_name')
    etree.SubElement(manual, f'{{{X}}}label', ref="jr:itext('list/manual_batch_name-label')")
    group.insert(list(group).index(one(group, './x:input[@ref="/data/list/other_explained"]')) + 1,
                 manual)
    group.remove(old)
    group.getparent().append(old)  # Separate page so the calculated number is refreshed on display.
    model.insert(list(model).index(one(model, './x:itext')),
                 etree.Element(f'{{{X}}}setvalue', event='xforms-ready',
                               ref='/data/list/registration_date', value='today()'))
    model.insert(list(model).index(one(model, './x:itext')),
                 etree.Element(f'{{{X}}}setvalue', event='xforms-ready',
                               ref='/data/list/batch_on_bed_today', value="'1'"))


def change_monitoring(root):
    data = one(root, '//x:model/x:instance/*')
    model = one(root, '//x:model')
    body = one(root, '//h:body')
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    close_question = one(body, './x:select1[@ref="/data/close_batch"]')
    choices = close_question.xpath('./x:item/x:value/text()', namespaces=NS)
    if choices != ['no', 'yes']:
        raise ValueError('Existing close choice values have changed')
    etree.SubElement(data, f'{{{data.nsmap[None]}}}confirm_close')
    model.insert(list(model).index(one(model, './x:itext')),
                 etree.Element(f'{{{X}}}bind', nodeset='/data/confirm_close',
                               relevant="/data/close_batch = 'yes'", required='true()',
                               constraint=". = 'yes'"))
    one(translation, './x:text[@id="close_batch-label"]/x:value').text = 'Is this drying-bed batch ready to close?'
    one(translation, './x:text[@id="close_batch-yes-label"]/x:value').text = 'Yes, close this batch'
    one(translation, './x:text[@id="monitoring/sample_code-label"]/x:value').text = (
        'Lab sample code, if a sample was taken (leave blank otherwise)')
    label(translation, 'confirm_close-label',
          'Confirm: all closing measurements are complete and this batch is ready to close.')
    label(translation, 'confirm_close-yes-label', 'I confirm')
    label(translation, 'confirm_close-no-label', 'Go back and check')
    confirm = select(body, '/data/confirm_close', 'confirm_close-label',
                     [('no', 'confirm_close-no-label'), ('yes', 'confirm_close-yes-label')])
    body.remove(confirm)
    body.insert(list(body).index(one(body, './x:group[@ref="/data/close"]')) + 1, confirm)


def preview(export, output_dir):
    forms = {record['form_id']: record for record in json.loads(Path(export).read_text(encoding='utf-8'))}
    if any(form_id not in forms for form_id in FORM_IDS.values()):
        raise ValueError('Both Safisana drying-bed forms must be present in the export')
    registration = forms[FORM_IDS['registration']]
    monitoring = forms[FORM_IDS['monitoring']]
    if (registration['case_type'] != monitoring['case_type'] or registration['case_type'] != 'dryingbed'
            or registration['open_case']['name_question'] != '/data/list/drying_bed_batch_name'
            or monitoring['close_case']['condition'] != {
                'type': 'if', 'question': '/data/close_batch', 'answer': 'yes', 'operator': '='}):
        raise ValueError('Live case mapping differs from the reviewed export')
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    for name, record, change in (('registration', registration, change_registration),
                                 ('monitoring', monitoring, change_monitoring)):
        if not record.get('xml'):
            raise ValueError(f'{name} has no source XML; export with --include-source')
        root = etree.parse(BytesIO(record['xml'].encode('utf-8'))).getroot()
        calculations_before = {e.get('nodeset'): e.get('calculate') for e in root.xpath('//x:bind[@calculate]', namespaces=NS)}
        change(root)
        calculations_after = {e.get('nodeset'): e.get('calculate') for e in root.xpath('//x:bind[@calculate]', namespaces=NS)}
        if any(calculations_after.get(path) != formula for path, formula in calculations_before.items()):
            raise ValueError(f'{name} modified an existing calculation')
        xml = etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        etree.fromstring(xml)
        (directory / f'drying-bed-{name}-preview.xml').write_bytes(xml)
    return directory


class Command(BaseCommand):
    help = 'Prepare reviewed Safisana drying-bed XML previews; never change live app data.'

    def add_arguments(self, parser):
        parser.add_argument('--workflow-export', required=True)
        parser.add_argument('--output-dir', required=True)

    def handle(self, workflow_export, output_dir, **options):
        try:
            path = preview(workflow_export, output_dir)
        except (OSError, ValueError, KeyError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Wrote review-only drying-bed XML previews to {path}')
