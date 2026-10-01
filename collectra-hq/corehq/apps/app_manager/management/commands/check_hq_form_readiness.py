"""Audit current editable applications without saving or releasing them."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.app_manager.form_readiness import inspect_form_xml
from corehq.apps.app_manager.xform import XForm, validate_xform


class Command(BaseCommand):
    help = 'Check current form blobs and XML; optionally validate with Formplayer. No app is saved.'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--app-id', action='append', dest='app_ids', default=[])
        parser.add_argument('--validate-xforms', action='store_true')
        parser.add_argument('--output', required=True)

    def handle(self, domain, app_ids, validate_xforms, output, **options):
        apps = list(get_apps_in_domain(domain, include_remote=False))
        selected = set(app_ids)
        if selected - {app._id for app in apps}:
            raise CommandError('Some selected applications do not exist in this domain')
        apps = [app for app in apps if not selected or app._id in selected]
        if not apps:
            raise CommandError('No editable applications found')
        records = []
        for app in sorted(apps, key=lambda app: (app.name, app._id)):
            for module in app.get_modules():
                for form in module.get_forms():
                    record = {'app_id': app._id, 'app_name': app.name,
                              'form_id': form.unique_id, 'form_name': form.default_name(),
                              'problems': [], 'engine_validation': 'not_requested'}
                    records.append(record)
                    if getattr(form, 'form_type', '') == 'shadow_form':
                        record['engine_validation'] = 'inherited_from_parent'
                        continue
                    try:
                        # Bypass lazy missing-file cache; never migrate legacy contents on read.
                        source = app.fetch_attachment(f'{form.unique_id}.xml')
                        record['problems'] = inspect_form_xml(source)
                        if validate_xforms:
                            record['engine_validation'] = 'blocked_by_xml' if record['problems'] else 'failed'
                            if not record['problems']:
                                xform = XForm(source, domain=domain)
                                xform.strip_vellum_ns_attributes()
                                validate_xform(etree.tostring(xform.xml, encoding='utf-8'))
                                record['engine_validation'] = 'passed'
                    except Exception as error:
                        record['problems'].append(f'{type(error).__name__}: {error}')
        report = {'domain': domain, 'applications': len(apps), 'forms': len(records),
                  'forms_with_problems': sum(bool(item['problems']) for item in records),
                  'engine_validation_requested': validate_xforms, 'results': records}
        path = Path(output).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(f"Applications: {len(apps)}; forms: {len(records)}; "
                          f"forms with problems: {report['forms_with_problems']}. Report: {output}")
        if not validate_xforms:
            self.stdout.write('Formplayer validation was not run. Use --validate-xforms before a presentation.')
        if report['forms_with_problems']:
            raise CommandError('Form readiness checks failed. See the report; no applications were changed.')
