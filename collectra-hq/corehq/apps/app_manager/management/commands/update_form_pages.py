"""Back up and update editable application forms in one domain."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.form_pages import upgrade_form_pages
from corehq.apps.app_manager.util import save_xform
from corehq.apps.app_manager.xform import XForm, validate_xform


class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--output-dir', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, domain, output_dir, apply=False, **options):
        directory = Path(output_dir)
        directory.mkdir(parents=True, exist_ok=True)
        plan = []
        report = []
        for app in get_apps_in_domain(domain, include_remote=False):
            changes = []
            for module in app.get_modules():
                for form in module.get_forms():
                    if form.form_type == 'shadow_form':
                        continue
                    source = app.fetch_attachment(form.unique_id + '.xml')
                    if not source.strip():
                        report.append({'app_id': app._id, 'app': app.name, 'form_id': form.unique_id,
                                       'form': form.name, 'changed': False, 'other_fields_added': [],
                                       'warnings': ['Empty form draft; no questions to update']})
                        continue
                    try:
                        revised, detail = upgrade_form_pages(source)
                    except ValueError as error:
                        raise CommandError(f'{app.name} / {form.name}: {error}') from error
                    report.append({'app_id': app._id, 'app': app.name, 'form_id': form.unique_id,
                                   'form': form.name, 'changed': revised != source, **detail})
                    if revised != source:
                        if apply:
                            wrapped = XForm(revised)
                            wrapped.strip_vellum_ns_attributes()
                            validate_xform(wrapped.render())
                        changes.append((form, source, revised))
            plan.append((app, changes))
        (directory / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        if apply:
            for app, changes in plan:
                if not changes:
                    continue
                app_dir = directory / app._id
                app_dir.mkdir(exist_ok=True)
                with (app_dir / 'application-before.json').open('x', encoding='utf-8') as backup:
                    json.dump(app.to_json(), backup)
                for form, source, revised in changes:
                    with (app_dir / (form.unique_id + '.xml')).open('xb') as backup:
                        backup.write(source)
                    save_xform(app, form, revised)
                app.save()
                for form, _, revised in changes:
                    if app.fetch_attachment(form.unique_id + '.xml') != revised:
                        raise CommandError(f'Saved source did not match: {form.unique_id}')
        self.stdout.write(json.dumps({'forms': len(report),
                                     'changed': sum(row['changed'] for row in report),
                                     'other_fields': sum(len(row['other_fields_added']) for row in report),
                                     'applied': apply}))
