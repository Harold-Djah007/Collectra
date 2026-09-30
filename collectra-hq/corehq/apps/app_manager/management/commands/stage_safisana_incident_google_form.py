"""Map the Safisana Google incident form into the existing incident workflow."""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import NS, X, one
from corehq.apps.app_manager.models.form_actions import ConditionalCaseUpdate
from corehq.apps.app_manager.util import save_xform


APP_ID = '43599346df8b71c72052e07e42b241cd'
FORM_ID = '0f99883b2c4e4aa287121086ef88fec3'
INCIDENT_XMLNS = 'http://openrosa.org/formdesigner/572431EB-BF57-4028-BEA3-21BECEABA4B9'
SPEC_PATH = Path(__file__).resolve().parents[2] / 'data/safisana_incident_google_form.json'
PREFIX = '/data/google_incident/'
LEGACY_DATETIME_CALCULATION = f"concat({PREFIX}incident_date, 'T', {PREFIX}incident_time)"
DATETIME_CALCULATION = (
    f"if({PREFIX}incident_date != '' and {PREFIX}incident_time != '', "
    f"{LEGACY_DATETIME_CALCULATION}, '')"
)
CASE_PROPERTIES = (
    'plant', 'department', 'department_other', 'reported_by', 'reported_by_other',
    'sio_eio', 'incident_kind', 'was_injured', 'injured_person', 'location',
    'incident_date', 'preventive_action', 'control_in_place', 'response_status',
)


def specification():
    return json.loads(SPEC_PATH.read_text(encoding='utf-8'))


def question_path(question):
    return question.get('path', PREFIX + question['id'])


def ensure_control_groups(root):
    """Give visible questions valid group parents in the form designer."""
    body = one(root, '//h:body')
    if body.xpath('./x:group[@ref="/data/google_incident"]', namespaces=NS):
        return False
    controls = [node for node in list(body)
                if node.get('ref', '').startswith(PREFIX)
                or node.get('ref') in ('/data/description/description', '/data/actions/immediate_action')]
    group = etree.Element(f'{{{X}}}group', ref='/data/google_incident')
    etree.SubElement(group, f'{{{X}}}label').text = 'Incident report'
    body.insert(0, group)
    for control in controls:
        path = control.get('ref')
        if path.startswith(PREFIX):
            group.append(control)
        else:
            parent_path = path.rsplit('/', 1)[0]
            matches = body.xpath('./x:group[@ref=$path]', namespaces=NS, path=parent_path)
            wrapper = matches[0] if matches else etree.Element(f'{{{X}}}group', ref=parent_path)
            # Retain extra legacy questions, including conditional first aid.
            wrapper.insert(0, control)
            group.append(wrapper)
    return True


def merged_case_updates(existing):
    updates = dict(existing)
    for key in CASE_PROPERTIES:
        path = PREFIX + key
        if key in updates:
            if updates[key].question_path != path:
                raise ValueError(f'Existing case property mapping differs: {key}')
        else:
            updates[key] = ConditionalCaseUpdate(question_path=path)
    return updates


def validate_source(root, spec):
    for question in spec['questions']:
        path = question_path(question)
        bind = one(root, f'//x:model/x:bind[@nodeset="{path}"]')
        control = one(root, f'//h:body//*[@ref="{path}"]')
        if bool(bind.get('required') == 'true()') != question['required']:
            raise ValueError(f'Required setting differs at {path}')
        if question.get('choices'):
            values = control.xpath('./x:item/x:value/text()', namespaces=NS)
            if etree.QName(control).localname != 'select1' or values != [v for v, _ in question['choices']]:
                raise ValueError(f'Answer choices differ at {path}')
        if question['type'] == 'date' and bind.get('type') != 'xsd:date':
            raise ValueError('The incident date must remain a date question')
        if question['type'] == 'file_upload' and control.get('mediatype') != 'image/*':
            raise ValueError('The proof question must use native photo capture')


def upgrade_source(source):
    """Preserve legacy paths and existing calculations, adding the source questions."""
    source = source.encode('utf-8') if isinstance(source, str) else source
    root = etree.fromstring(source)
    spec = specification()
    model = one(root, '//x:model')
    data = one(model, './x:instance/*')
    body = one(root, '//h:body')
    if etree.QName(data).namespace != INCIDENT_XMLNS:
        raise ValueError('This is not the reviewed Safisana incident registration form')
    if data.xpath('./*[local-name()="google_incident"]'):
        validate_source(root, spec)
        date_time = one(model, './x:bind[@nodeset="/data/time_type/date_time"]')
        changed = False
        if date_time.get('calculate') == LEGACY_DATETIME_CALCULATION:
            date_time.set('calculate', DATETIME_CALCULATION)
            changed = True
        elif date_time.get('calculate') != DATETIME_CALCULATION:
            raise ValueError('The incident timestamp calculation changed; review manually')
        changed = ensure_control_groups(root) or changed
        if changed:
            return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
        return source
    old_paths = set(model.xpath('./x:bind/@nodeset', namespaces=NS))
    formulas = {b.get('nodeset'): b.get('calculate')
                for b in model.xpath('./x:bind[@calculate]', namespaces=NS)}
    for path, expected_type in (('/data/time_type/date_time', 'xsd:dateTime'),
                                ('/data/time_type/name', 'xsd:string'),
                                ('/data/description/description', 'xsd:string'),
                                ('/data/actions/immediate_action', 'xsd:string')):
        if one(model, f'./x:bind[@nodeset="{path}"]').get('type') != expected_type:
            raise ValueError(f'An existing field type changed at {path}; review manually')
    for path in ('/data/time_type/date_time', '/data/description/type_incident'):
        if one(model, f'./x:bind[@nodeset="{path}"]').get('calculate'):
            raise ValueError(f'An existing calculation at {path} cannot be replaced')

    translation = one(model, './x:itext/x:translation[@lang="en"]')
    group = etree.SubElement(data, f'{{{INCIDENT_XMLNS}}}google_incident')

    def text(identifier, wording):
        if translation.xpath('./x:text[@id=$id]', namespaces=NS, id=identifier):
            raise ValueError(f'Translation ID already exists: {identifier}')
        item = etree.SubElement(translation, f'{{{X}}}text', id=identifier)
        etree.SubElement(item, f'{{{X}}}value').text = wording

    def bind(path, **attributes):
        node = etree.Element(f'{{{X}}}bind', nodeset=path, **attributes)
        model.insert(list(model).index(one(model, './x:itext')), node)
        return node

    def field(name, **attributes):
        etree.SubElement(group, f'{{{INCIDENT_XMLNS}}}{name}')
        return bind(PREFIX + name, **attributes)

    bind('/data/google_incident')
    field('source_version', calculate=f"'{spec['version']}'")
    # Remove only the controls being replaced; extra/custom controls remain.
    for path in ('/data/time_type/date_time', '/data/description/type_incident',
                 '/data/description/description', '/data/actions/immediate_action'):
        node = one(body, f'.//*[@ref="{path}"]')
        node.getparent().remove(node)

    controls = []
    for question in spec['questions']:
        path = question_path(question)
        kind = question['type']
        attrs = {'required': 'true()'} if question['required'] else {}
        if kind in ('short_text', 'paragraph'):
            attrs['type'] = 'xsd:string'
        elif kind == 'date':
            attrs['type'] = 'xsd:date'
        elif kind == 'file_upload':
            attrs['type'] = 'binary'
        if question.get('path'):
            existing = one(model, f'./x:bind[@nodeset="{path}"]')
            for key, value in attrs.items():
                existing.set(key, value)
        else:
            field(question['id'], **attrs)
        tag = 'select1' if question.get('choices') else ('upload' if kind == 'file_upload' else 'input')
        control = etree.Element(f'{{{X}}}{tag}', ref=path)
        if kind == 'dropdown':
            control.set('appearance', 'minimal')
        if kind == 'paragraph':
            control.set('appearance', 'multiline')
        if kind == 'file_upload':
            control.set('mediatype', 'image/*')
        identifier = 'google-incident-' + question['id']
        text(identifier, question['label'])
        etree.SubElement(control, f'{{{X}}}label', ref=f"jr:itext('{identifier}')")
        if question.get('hint'):
            text(identifier + '-hint', question['hint'])
            etree.SubElement(control, f'{{{X}}}hint', ref=f"jr:itext('{identifier}-hint')")
        for value, label in question.get('choices', []):
            item = etree.SubElement(control, f'{{{X}}}item')
            text(identifier + '-' + value, label)
            etree.SubElement(item, f'{{{X}}}label', ref=f"jr:itext('{identifier}-{value}')")
            etree.SubElement(item, f'{{{X}}}value').text = value
        controls.append(control)
        if question.get('default'):
            etree.SubElement(model, f'{{{X}}}setvalue', event='xforms-ready', ref=path,
                             value=f"'{question['default']}'")
        if question.get('other'):
            name = question['id'] + '_other'
            field(name, type='xsd:string', required='true()', relevant=f"{path} = 'other'")
            other = etree.Element(f'{{{X}}}input', ref=PREFIX + name)
            text(identifier + '-other-detail', 'Please specify')
            etree.SubElement(other, f'{{{X}}}label', ref=f"jr:itext('{identifier}-other-detail')")
            controls.append(other)
        if question['id'] == 'incident_date':
            field('incident_time', type='xsd:time', required='true()')
            time = etree.Element(f'{{{X}}}input', ref=PREFIX + 'incident_time')
            text('google-incident-time', 'What time did the incident happen?')
            etree.SubElement(time, f'{{{X}}}label', ref="jr:itext('google-incident-time')")
            controls.append(time)

    # Existing case/export properties retain their paths, types and value codes.
    one(model, './x:bind[@nodeset="/data/time_type/date_time"]').set(
        'calculate', DATETIME_CALCULATION)
    one(model, './x:bind[@nodeset="/data/description/type_incident"]').set(
        'calculate', f"if({PREFIX}was_injured = 'yes', 'injury', {PREFIX}incident_kind)")
    bind('/data/needs_attention', calculate="'yes'")
    bind('/data/attention_note', calculate='/data/description/description', type='xsd:string')
    etree.SubElement(data, f'{{{INCIDENT_XMLNS}}}needs_attention')
    etree.SubElement(data, f'{{{INCIDENT_XMLNS}}}attention_note')
    for index, control in enumerate(controls):
        body.insert(index, control)
    for node in list(body):
        if etree.QName(node).localname == 'group' and not node.xpath(
                './/x:input | .//x:select | .//x:select1 | .//x:upload | .//x:trigger', namespaces=NS):
            body.remove(node)
    ensure_control_groups(root)
    for path, formula in formulas.items():
        if one(model, f'./x:bind[@nodeset="{path}"]').get('calculate') != formula:
            raise ValueError(f'Existing calculation changed: {path}')
    if not old_paths <= set(model.xpath('./x:bind/@nodeset', namespaces=NS)):
        raise ValueError('An existing export field was removed')
    validate_source(root, spec)
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)


class Command(BaseCommand):
    help = 'Preview or stage all 15 Google incident questions in the existing incident registration draft.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply=False, **options):
        try:
            app = get_app('safisana', APP_ID)
            form = app.get_form(FORM_ID)
            if (form.actions.open_case.condition.type != 'always'
                    or form.actions.open_case.name_update.question_path != '/data/time_type/name'):
                raise ValueError('The incident case registration mapping changed; review manually')
            original = app.fetch_attachment(FORM_ID + '.xml')
            revised = upgrade_source(original)
            updates = merged_case_updates(form.actions.update_case.update)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'incident-google-form-preview.xml'
            preview.write_bytes(revised)
            self.stdout.write(f'Validated 15 source questions and legacy incident mappings: {preview}')
            self.stdout.write('Proof uses native photo upload; the Google general-file picker/10 MB cap is not imported.')
            if not apply:
                self.stdout.write('Preview only. Pass --apply to save the editable application draft.')
                return
            if revised != original or updates != dict(form.actions.update_case.update):
                backup = directory / f'{APP_ID}-{FORM_ID}-{hashlib.sha256(original).hexdigest()}.xml'
                if backup.exists():
                    if backup.read_bytes() != original:
                        raise ValueError('The existing backup has different content')
                else:
                    with backup.open('xb') as file:
                        file.write(original)
                form.actions.update_case.update = updates
                save_xform(app, form, revised)
                app.save()
                if get_app('safisana', APP_ID).fetch_attachment(FORM_ID + '.xml') != revised:
                    raise ValueError('Saved incident XML did not match the preview')
            self.stdout.write('Incident registration draft saved and verified. No mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
