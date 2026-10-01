"""Restore the reviewed operational questions after recovering older form XML."""

import hashlib
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import (
    FORM_IDS, MORNING_STATUS_LABELS, NS, STATUS_VALUES, add_attention_questions,
    add_morning_issue_notes, one, refine_staged_morning_choices,
)
from corehq.apps.app_manager.util import save_xform


APP_ID = '43599346df8b71c72052e07e42b241cd'
FORM_NAMES = {'morning-checks': 'Morning Checks Daily', 'metering-round': 'Metering Round'}


def upgrade_source(source, form_name):
    """Upgrade reviewed legacy XML, or validate an already upgraded form."""
    source = source.encode('utf-8') if isinstance(source, str) else source
    root = etree.fromstring(source)
    formulas = {
        bind.get('nodeset'): bind.get('calculate')
        for bind in root.xpath('//x:model/x:bind[@calculate]', namespaces=NS)
    }
    paths = set(root.xpath('//x:model/x:bind/@nodeset', namespaces=NS))
    namespace = etree.QName(one(root, '//x:model/x:instance/*')).namespace
    changed = False
    if '/data/needs_attention' not in paths:
        add_attention_questions(root, form_name)
        changed = True

    if form_name == 'Morning Checks Daily':
        choices = [
            one(root, f'//h:body//x:select1[@ref="{path}"]')
            for path in MORNING_STATUS_LABELS
        ]
        values = [choice.xpath('./x:item/x:value/text()', namespaces=NS) for choice in choices]
        if all(value == [*STATUS_VALUES, 'not_applicable'] for value in values):
            refine_staged_morning_choices(root)
            changed = True
        elif not all(value == list(STATUS_VALUES) for value in values):
            raise ValueError('Morning Checks has an unreviewed or mixed answer-choice version')

        note_paths = {path.removesuffix('_status') + '_issue_note' for path in MORNING_STATUS_LABELS}
        existing_notes = set(root.xpath('//x:model/x:bind/@nodeset', namespaces=NS)) & note_paths
        if not existing_notes:
            add_morning_issue_notes(root)
            changed = True
        elif existing_notes != note_paths:
            raise ValueError('Morning Checks has only some issue-note fields; review it manually')
        for path in MORNING_STATUS_LABELS:
            note_path = path.removesuffix('_status') + '_issue_note'
            bind = one(root, f'//x:model/x:bind[@nodeset="{note_path}"]')
            one(root, f'//h:body//x:input[@ref="{note_path}"]')
            if bind.get('relevant') != f"{path} = 'needs_attention'" or bind.get('required') != 'true()':
                raise ValueError(f'{note_path} has different issue-note rules; review it manually')

    for field in ('needs_attention', 'attention_severity', 'attention_note'):
        one(root, f'//x:model/x:bind[@nodeset="/data/{field}"]')
    for field in ('attention_severity', 'attention_note'):
        one(root, f'//h:body//*[@ref="/data/{field}"]')
    for path, formula in formulas.items():
        if one(root, f'//x:model/x:bind[@nodeset="{path}"]').get('calculate') != formula:
            raise ValueError(f'Existing calculation changed at {path}')
    if not paths <= set(root.xpath('//x:model/x:bind/@nodeset', namespaces=NS)):
        raise ValueError('An existing field path was removed')
    if etree.QName(one(root, '//x:model/x:instance/*')).namespace != namespace:
        raise ValueError('The submission namespace changed')
    return (etree.tostring(root, encoding='UTF-8', xml_declaration=True, pretty_print=True)
            if changed else source)


class Command(BaseCommand):
    help = 'Preview or repair the two editable operational forms, with exact current XML backups.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply=False, **options):
        try:
            app = get_app('safisana', APP_ID)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            pending = []
            # Read actual blobs and validate BOTH forms before staging either.
            for slug, form_id in FORM_IDS.items():
                original = app.fetch_attachment(form_id + '.xml')
                revised = upgrade_source(original, FORM_NAMES[slug])
                preview = directory / f'{slug}-dashboard-ready-preview.xml'
                preview.write_bytes(revised)
                self.stdout.write(f'{FORM_NAMES[slug]}: '
                                  f'{"ready" if revised == original else "upgrade prepared"}; {preview}')
                if revised != original:
                    pending.append((form_id, original, revised))
            if not apply:
                self.stdout.write('Preview only. Pass --apply to save the editable draft.')
                return
            backups = directory / 'original-xml-backups'
            backups.mkdir(exist_ok=True)
            for form_id, original, revised in pending:
                digest = hashlib.sha256(original).hexdigest()
                backup = backups / f'{APP_ID}-{form_id}-{digest}.xml'
                if backup.exists():
                    if backup.read_bytes() != original:
                        raise ValueError(f'Backup content mismatch: {backup}')
                else:
                    with backup.open('xb') as file:
                        file.write(original)
            for form_id, original, revised in pending:
                save_xform(app, app.get_form(form_id), revised)
            if pending:
                app.save()
                verify_app = get_app('safisana', APP_ID)
                for form_id, original, revised in pending:
                    if verify_app.fetch_attachment(form_id + '.xml') != revised:
                        raise ValueError(f'Saved form verification failed: {form_id}')
            self.stdout.write(f'Validated both operational forms; saved {len(pending)} upgrades. '
                              'No mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
