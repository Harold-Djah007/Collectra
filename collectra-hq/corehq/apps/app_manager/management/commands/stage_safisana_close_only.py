"""Preview a dedicated drying-bed close form, preserving legacy measurements."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.preview_safisana_drying_bed import (
    FORM_IDS, NS, X, one,
)
from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID, H


XMLNS = 'http://openrosa.org/formdesigner/97A64BD5-760A-4A0C-A62B-8BF887F689E1'
FORM_NAME = 'Close drying-bed batch'


def build_close_form():
    root = etree.Element(f'{{{H}}}html', nsmap={'h': H, None: X,
                                               'xsd': 'http://www.w3.org/2001/XMLSchema'})
    head = etree.SubElement(root, f'{{{H}}}head')
    etree.SubElement(head, f'{{{H}}}title').text = FORM_NAME
    model = etree.SubElement(head, f'{{{X}}}model')
    instance = etree.SubElement(model, f'{{{X}}}instance')
    data = etree.SubElement(instance, f'{{{XMLNS}}}data', nsmap={None: XMLNS})
    data.attrib.update({'name': FORM_NAME, 'uiVersion': '1', 'version': '1'})
    for field in ('notice', 'confirm_close', 'reason'):
        etree.SubElement(data, f'{{{XMLNS}}}{field}')
        attrs = {'nodeset': f'/data/{field}', 'type': 'xsd:string'}
        if field in ('confirm_close', 'reason'):
            attrs['required'] = 'true()'
        if field == 'confirm_close':
            attrs['constraint'] = ". = 'yes'"
        etree.SubElement(model, f'{{{X}}}bind', **attrs)
    body = etree.SubElement(root, f'{{{H}}}body')
    notice = etree.SubElement(body, f'{{{X}}}trigger', ref='/data/notice')
    etree.SubElement(notice, f'{{{X}}}label').text = (
        'Save all final drying-bed measurements in Drying Bed monitoring before closing this case.')
    confirm = etree.SubElement(body, f'{{{X}}}select1', ref='/data/confirm_close')
    etree.SubElement(confirm, f'{{{X}}}label').text = 'Is this batch ready to close?'
    for value, label in [('yes', 'Yes, close this batch'), ('no', 'No, return to monitoring')]:
        item = etree.SubElement(confirm, f'{{{X}}}item')
        etree.SubElement(item, f'{{{X}}}label').text = label
        etree.SubElement(item, f'{{{X}}}value').text = value
    reason = etree.SubElement(body, f'{{{X}}}input', ref='/data/reason')
    etree.SubElement(reason, f'{{{X}}}label').text = 'Reason for closing this batch'
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


def change_monitoring_source(xml):
    root = etree.fromstring(xml.encode('utf-8') if isinstance(xml, str) else xml)
    model = one(root, '//x:model')
    translation = one(model, './x:itext/x:translation[@lang="en"]')
    close_question = one(root, '//h:body/x:select1[@ref="/data/close_batch"]')
    if close_question.xpath('./x:item/x:value/text()', namespaces=NS) != ['no', 'yes']:
        raise ValueError('The reviewed close question choices have changed')
    old_formulas = {bind.get('nodeset'): bind.get('calculate')
                    for bind in model.xpath('./x:bind[@calculate]', namespaces=NS)}
    one(translation, './x:text[@id="close_batch-label"]/x:value').text = (
        'Are you recording the final batch measurements now? The case will stay open until'
        ' you submit Close drying-bed batch.')
    one(translation, './x:text[@id="close_batch-yes-label"]/x:value').text = (
        'Yes, record final measurements')
    one(translation, './x:text[@id="close_batch-no-label"]/x:value').text = (
        'No, continue monitoring')
    new_formulas = {bind.get('nodeset'): bind.get('calculate')
                    for bind in model.xpath('./x:bind[@calculate]', namespaces=NS)}
    if new_formulas != old_formulas:
        raise ValueError('An existing calculation was changed')
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


def preview_and_optionally_stage(output_dir, apply=False):
    app = get_app('safisana', APP_ID)
    module = next((module for module in app.get_modules()
                   if any(form.unique_id == FORM_IDS['monitoring'] for form in module.get_forms())), None)
    if module is None or module.case_type != 'dryingbed' or 'en' not in app.langs:
        raise ValueError('The reviewed English drying-bed module was not found')
    monitoring = next(form for form in module.get_forms()
                      if form.unique_id == FORM_IDS['monitoring'])
    condition = monitoring.actions.close_case.condition
    if (monitoring.requires != 'case' or condition.type != 'if'
            or condition.question != '/data/close_batch' or condition.answer != 'yes'
            or condition.operator != '='):
        raise ValueError('The monitoring closure mapping differs from the reviewed configuration')
    if any(form.default_name() == FORM_NAME or form.xmlns == XMLNS
           for form in module.get_forms()):
        raise ValueError('A dedicated closing form already exists in this module')

    monitoring_xml = change_monitoring_source(monitoring.source)
    close_xml = build_close_form()
    etree.fromstring(close_xml)
    directory = Path(output_dir).expanduser()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'drying-bed-monitoring-close-only-preview.xml').write_bytes(monitoring_xml)
    (directory / 'drying-bed-close-only-preview.xml').write_bytes(close_xml)
    (directory / 'drying-bed-close-only-plan.json').write_text(json.dumps({
        'app_id': APP_ID,
        'module_id': module.unique_id,
        'case_type': module.case_type,
        'monitoring_form_id': monitoring.unique_id,
        'monitoring_close_action_after': 'never',
        'new_form_name': FORM_NAME,
        'new_form_requires': 'case',
        'new_form_close_action': 'always',
        'existing_case_ids_and_calculations': 'unchanged',
        'published_mobile_build': False,
    }, indent=2), encoding='utf-8')
    if not apply:
        return directory
    backup = directory / f'{APP_ID}-before-close-only.json'
    with backup.open('x', encoding='utf-8') as handle:
        json.dump(app.to_json(), handle, ensure_ascii=False, indent=2, default=str)
    monitoring.source = monitoring_xml.decode('utf-8')
    condition.type = 'never'
    condition.question = None
    condition.answer = None
    new_form = app.new_form(module.id, FORM_NAME, 'en', attachment=close_xml.decode('utf-8'))
    new_form.requires = 'case'
    new_form.actions.close_case.condition.type = 'always'
    for form in (new_form, monitoring):
        rendered = form.render_xform()
        etree.fromstring(rendered.encode('utf-8') if isinstance(rendered, str) else rendered)
    app.save()
    return directory


class Command(BaseCommand):
    help = 'Preview or stage a separate drying-bed close action; no mobile build is published.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply, **options):
        try:
            directory = preview_and_optionally_stage(output_dir, apply)
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f'Wrote drying-bed close-only previews to {directory}')
        if apply:
            self.stdout.write('Saved editable app draft; no mobile build was released.')
        else:
            self.stdout.write('No application document was changed.')
