"""Stage reviewed question upgrades in editable Safisana apps, without releasing.

The export is a concurrency guard: an app form edited since the export is
rejected before any changes are written. Original XML is backed up locally.
"""

import hashlib
import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.management.commands import (
    preview_safisana_alert_forms as attention,
    preview_safisana_choice_cleanup as choices,
)
from corehq.apps.app_manager.util import save_xform


def upgrades(workflow_export, output_dir):
    """Generate the previews from the original export and return form mapping."""
    attention.preview(workflow_export, output_dir)
    choices.preview(workflow_export, output_dir)
    result = {
        form_id: f'{slug}-attention-preview.xml'
        for slug, form_id in attention.FORM_IDS.items()
    }
    result.update({
        form_id: f'{slug}-choice-preview.xml'
        for form_id, (slug, _) in choices.QUESTIONS.items()
    })
    return result


class Command(BaseCommand):
    help = ('Check reviewed question upgrades against current Safisana forms; '
            'with --apply save only editable app drafts, never release a build.')

    def add_arguments(self, parser):
        parser.add_argument('--workflow-export', required=True)
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, workflow_export, output_dir, apply, **options):
        directory = Path(output_dir).expanduser()
        try:
            source = json.loads(Path(workflow_export).expanduser().read_text(encoding='utf-8'))
            originals = {record['form_id']: record for record in source}
            filenames = upgrades(workflow_export, directory)
            pending = []
            apps = {}
            for form_id, filename in filenames.items():
                record = originals[form_id]
                if not record.get('xml'):
                    raise ValueError(f'{form_id} has no original XML')
                app = apps.setdefault(record['app_id'], None)
                if app is None:
                    app = apps[record['app_id']] = get_app('safisana', record['app_id'])
                form = app.get_form(form_id)
                original = record['xml']
                if form.source != original:
                    raise ValueError(f'{form_id} differs from the export; regenerate it before staging')
                upgraded = (directory / filename).read_bytes()
                if hashlib.sha256(original.encode('utf-8')).digest() == hashlib.sha256(upgraded).digest():
                    raise ValueError(f'{form_id} has no upgrade')
                pending.append((app, form_id, original, upgraded))
            self.stdout.write(f'Preflight passed for {len(pending)} forms in '
                              f'{len(set(app._id for app, _, _, _ in pending))} editable apps.')
            if not apply:
                self.stdout.write('Preview only. No application documents were changed.')
                return
            backup_dir = directory / 'original-xml-backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            for app, form_id, original, _ in pending:
                backup = backup_dir / f'{app._id}-{form_id}.xml'
                # Existing backups must remain intact across repeated runs.
                with backup.open('x', encoding='utf-8') as file:
                    file.write(original)
            for app, form_id, _, upgraded in pending:
                save_xform(app, app.get_form(form_id), upgraded)
            for app in apps.values():
                app.save()
                self.stdout.write(f'Staged {app.name}')
            self.stdout.write('Drafts saved. No app build was released and no existing cases were changed.')
        except (KeyError, OSError, ValueError) as error:
            raise CommandError(str(error)) from error
