"""Generate eight-digit drying-bed case names without worker text entry."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.preview_safisana_drying_bed import NS, X, one
from corehq.apps.app_manager.models.form_actions import ConditionalCaseUpdate
from corehq.apps.app_manager.util import save_xform


APP_ID = '43599346df8b71c72052e07e42b241cd'
FORM_ID = '49bde2379a3a4ee888bcce8b1e690b2f'
XMLNS = 'http://openrosa.org/formdesigner/411E5E9D-43B2-491C-ADE7-698B1678831E'
LEGACY_NAME = '/data/list/drying_bed_batch_name'
GENERATED_NAME = '/data/list/generated_batch_name'
DATE = '/data/list/registration_date'
BED = '/data/list/drying_bed_nmbr'
BED_CODES = {f'dry_bed_{number}': f'{number:02d}' for number in range(1, 7)}
bed_expression = "''"
for value, code in reversed(list(BED_CODES.items())):
    bed_expression = f"if({BED} = '{value}', '{code}', {bed_expression})"
NAME_CALCULATION = (
    f"if({DATE} != '' and ({bed_expression}) != '', "
    f"concat(format-date({DATE}, '%y%m%d'), {bed_expression}), '')"
)


def repair_hidden_date_bind(model):
    """Hidden values cannot have Required or Validation Condition settings."""
    date_bind = one(model, f'./x:bind[@nodeset="{DATE}"]')
    changed = False
    for attribute in ('required', 'constraint'):
        for key in (attribute, '{http://commcarehq.org/xforms/vellum}' + attribute):
            if key in date_bind.attrib:
                del date_bind.attrib[key]
                changed = True
    return changed


def upgrade_source(source):
    source = source.encode('utf-8') if isinstance(source, str) else source
    root = etree.fromstring(source)
    model = one(root, '//x:model')
    data = one(model, './x:instance/*')
    if etree.QName(data).namespace != XMLNS:
        raise ValueError('This is not the reviewed drying-bed registration form')
    body = one(root, '//h:body')
    bed = one(body, f'.//x:select1[@ref="{BED}"]')
    if root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=GENERATED_NAME):
        if (one(model, f'./x:bind[@nodeset="{GENERATED_NAME}"]').get('calculate') != NAME_CALCULATION
                or one(model, f'./x:bind[@nodeset="{LEGACY_NAME}"]').get('calculate')
                != f'int({GENERATED_NAME})'
                or bed.xpath('./x:item/x:value/text()', namespaces=NS) != list(BED_CODES)
                or one(model, f'./x:bind[@nodeset="{GENERATED_NAME}"]').get('readonly') != 'true()'
                or model.xpath('./x:setvalue[@ref=$path]/@value', namespaces=NS, path=DATE) != ['today()']
                or body.xpath('.//*[@ref=$path]', path=DATE)
                or body.xpath('.//*[@ref=$path]', path=LEGACY_NAME)):
            raise ValueError('The staged naming fields changed; review manually')
        if repair_hidden_date_bind(model):
            return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        return source
    if bed.xpath('./x:item/x:value/text()', namespaces=NS) != list(BED_CODES) + ['other']:
        raise ValueError('The reviewed bed choices changed; review manually')
    name_bind = one(model, f'./x:bind[@nodeset="{LEGACY_NAME}"]')
    if name_bind.get('type') != 'xsd:int' or name_bind.get('calculate'):
        raise ValueError('Existing batch-name type or calculation changed; review manually')
    lst = one(data, './*[local-name()="list"]')
    for name in ('registration_date', 'generated_batch_name'):
        if lst.xpath('./*[local-name()=$name]', name=name):
            raise ValueError(f'Existing field conflicts with the upgrade: {name}')
    formulas = {bind.get('nodeset'): bind.get('calculate')
                for bind in model.xpath('./x:bind[@calculate]', namespaces=NS)}
    paths = set(model.xpath('./x:bind/@nodeset', namespaces=NS))
    translation = one(model, './x:itext/x:translation[@lang="en"]')

    def label(identifier, wording):
        if translation.xpath('./x:text[@id=$id]', namespaces=NS, id=identifier):
            raise ValueError(f'Existing label conflicts with the upgrade: {identifier}')
        text = etree.SubElement(translation, f'{{{X}}}text', id=identifier)
        etree.SubElement(text, f'{{{X}}}value').text = wording

    def bind(path, **attrs):
        node = etree.Element(f'{{{X}}}bind', nodeset=path, **attrs)
        model.insert(list(model).index(one(model, './x:itext')), node)
        return node

    for name in ('registration_date', 'generated_batch_name'):
        etree.SubElement(lst, f'{{{XMLNS}}}{name}')
    bind(DATE, type='xsd:date', readonly='true()')
    bind(GENERATED_NAME, type='xsd:string', calculate=NAME_CALCULATION,
         readonly='true()', required='true()')
    # Keep the historical numeric export field; the case name uses a string
    # so dates in 2000-2009 retain their leading zeroes.
    name_bind.set('calculate', f'int({GENERATED_NAME})')
    name_bind.set('readonly', 'true()')
    bed_bind = one(model, f'./x:bind[@nodeset="{BED}"]')
    if bed_bind.get('constraint'):
        raise ValueError('The bed selection has a custom constraint; review manually')
    bed_bind.set('required', 'true()')
    bed_bind.set('constraint', ' or '.join(f". = '{value}'" for value in BED_CODES))
    for item in bed.xpath('./x:item', namespaces=NS):
        if item.xpath('./x:value/text()', namespaces=NS) == ['other']:
            bed.remove(item)
    bed.set('appearance', 'minimal')
    old = one(body, f'.//x:input[@ref="{LEGACY_NAME}"]')
    old.getparent().remove(old)
    label('collectra-generated-batch-name', 'Batch name (generated automatically)')
    generated = etree.SubElement(body, f'{{{X}}}input', ref=GENERATED_NAME)
    etree.SubElement(generated, f'{{{X}}}label', ref="jr:itext('collectra-generated-batch-name')")
    # The confirmation page follows the inputs so the calculation is refreshed.
    model.insert(list(model).index(one(model, './x:itext')),
                 etree.Element(f'{{{X}}}setvalue', event='xforms-ready', ref=DATE, value='today()'))
    if not paths <= set(model.xpath('./x:bind/@nodeset', namespaces=NS)):
        raise ValueError('An existing field was removed')
    for path, formula in formulas.items():
        if one(model, f'./x:bind[@nodeset="{path}"]').get('calculate') != formula:
            raise ValueError(f'Existing calculation changed: {path}')
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


class Command(BaseCommand):
    help = 'Preview or stage automatic today + two-digit bed names in the drying-bed registration draft.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply=False, **options):
        try:
            app = get_app('safisana', APP_ID)
            form = app.get_form(FORM_ID)
            mapping = form.actions.open_case.name_update
            if (form.actions.open_case.condition.type != 'always'
                    or mapping.question_path not in (LEGACY_NAME, GENERATED_NAME)):
                raise ValueError('The registration case-name mapping changed; review manually')
            original = app.fetch_attachment(FORM_ID + '.xml')
            revised = upgrade_source(original)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'drying-bed-eight-digit-names-preview.xml'
            preview.write_bytes(revised)
            self.stdout.write(f'Validated date + bed selection; example 2026-09-30 / Bed 1 = 26093001. Preview: {preview}')
            if not apply:
                self.stdout.write('Preview only. Pass --apply to save the draft.')
                return
            if revised != original or mapping.question_path != GENERATED_NAME:
                snapshot = {'xml': original.decode('utf-8'), 'name_update': mapping.to_json()}
                backup = directory / f'{APP_ID}-{FORM_ID}-{hashlib.sha256(original).hexdigest()}-naming-backup.json'
                if not backup.exists():
                    with backup.open('x', encoding='utf-8') as file:
                        json.dump(snapshot, file, ensure_ascii=False, indent=2)
                form.actions.open_case.name_update = ConditionalCaseUpdate(
                    question_path=GENERATED_NAME, update_mode=mapping.update_mode)
                save_xform(app, form, revised)
                app.save()
                saved = get_app('safisana', APP_ID)
                if (saved.fetch_attachment(FORM_ID + '.xml') != revised
                        or saved.get_form(FORM_ID).actions.open_case.name_update.question_path != GENERATED_NAME):
                    raise ValueError('Saved XML or case-name mapping differs from the preview')
            self.stdout.write('Saved eight-digit batch-name draft. Existing cases were not renamed; no mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
