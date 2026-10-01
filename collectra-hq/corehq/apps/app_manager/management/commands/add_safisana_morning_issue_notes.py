"""Preview or save contextual issue notes in the editable Morning Checks draft."""

import hashlib
from io import BytesIO
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import (
    FORM_IDS, NS, add_morning_issue_notes,
)
from corehq.apps.app_manager.util import save_xform


APP_ID = '43599346df8b71c72052e07e42b241cd'
FORM_ID = FORM_IDS['morning-checks']


class Command(BaseCommand):
    help = 'Add conditional issue notes to the 12 reviewed Morning Checks answers.'

    def add_arguments(self, parser):
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, output_dir, apply, **options):
        try:
            app = get_app('safisana', APP_ID)
            form = app.get_form(FORM_ID)
            original = form.source.encode('utf-8')
            root = etree.parse(BytesIO(original)).getroot()
            existing_binds = [etree.tostring(bind) for bind in root.xpath('//x:model/x:bind', namespaces=NS)]
            add_morning_issue_notes(root)
            revised_binds = [etree.tostring(bind) for bind in root.xpath('//x:model/x:bind', namespaces=NS)]
            # The original binds must remain verbatim and in order.
            if not all(any(bind == current for current in revised_binds)
                       for bind in existing_binds):
                raise ValueError('An existing form binding changed')
            revised = etree.tostring(root, xml_declaration=True, encoding='UTF-8', pretty_print=True)
            etree.fromstring(revised)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            preview = directory / 'morning-checks-issue-notes-preview.xml'
            preview.write_bytes(revised)
            self.stdout.write(f'Validated 12 conditional issue notes. Preview: {preview}')
            if not apply:
                self.stdout.write('No application document was changed.')
                return
            backup_dir = directory / 'original-xml-backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(original).hexdigest()[:12]
            backup = backup_dir / f'{APP_ID}-{FORM_ID}-{digest}-before-issue-notes.xml'
            with backup.open('xb') as file:
                file.write(original)
            save_xform(app, form, revised)
            app.save()
            self.stdout.write('Saved editable Morning Checks draft; no mobile build was released.')
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
