"""Compare a saved Safisana baseline with the editable application without changing data."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import (
    get_app, get_build_doc_by_version, wrap_app,
)
from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import APP_ID


X = {'x': 'http://www.w3.org/2002/xforms'}


def form_contract(form):
    root = etree.fromstring(form.source.encode('utf-8'))
    return {
        'name': form.default_name(),
        'xmlns': form.xmlns,
        'fields': {
            bind.get('nodeset'): {
                'type': bind.get('type'),
                'calculate': bind.get('calculate'),
                'constraint': bind.get('constraint'),
            }
            for bind in root.xpath('//x:model/x:bind[@nodeset]', namespaces=X)
        },
    }


def app_contract(app):
    return {
        form.unique_id: form_contract(form)
        for module in app.get_modules() for form in module.get_forms()
    }


def compare_contracts(before, after):
    changes = []
    for form_id in sorted(before.keys() & after.keys()):
        old, new = before[form_id], after[form_id]
        if old['xmlns'] != new['xmlns']:
            changes.append({'form_id': form_id, 'kind': 'xmlns',
                            'before': old['xmlns'], 'after': new['xmlns']})
        for path in sorted(old['fields'].keys() & new['fields'].keys()):
            for key in ('type', 'calculate', 'constraint'):
                if old['fields'][path][key] != new['fields'][path][key]:
                    changes.append({'form_id': form_id, 'path': path, 'kind': key,
                                    'before': old['fields'][path][key],
                                    'after': new['fields'][path][key]})
    return {
        'baseline_forms': len(before), 'current_forms': len(after),
        'removed_form_ids': sorted(before.keys() - after.keys()),
        'added_form_ids': sorted(after.keys() - before.keys()),
        'removed_field_paths': [
            {'form_id': form_id, 'path': path}
            for form_id in sorted(before.keys() & after.keys())
            for path in sorted(before[form_id]['fields'].keys() - after[form_id]['fields'].keys())
        ],
        'changes_to_existing_fields': changes,
    }


class Command(BaseCommand):
    help = 'Read-only comparison of a saved Processing - Plant build with its editable app.'

    def add_arguments(self, parser):
        parser.add_argument('--baseline-version', type=int, required=True)
        parser.add_argument('--output', required=True)

    def handle(self, baseline_version, output, **options):
        try:
            saved = get_build_doc_by_version('safisana', APP_ID, baseline_version)
            if not saved:
                raise ValueError(f'Build version {baseline_version} was not found')
            report = compare_contracts(
                app_contract(wrap_app(saved)), app_contract(get_app('safisana', APP_ID)))
            report['baseline_version'] = baseline_version
            path = Path(output).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
            self.stdout.write(f'Saved read-only compatibility report: {path}')
            self.stdout.write(f"Existing-field changes: {len(report['changes_to_existing_fields'])}")
            self.stdout.write(f"Removed field paths: {len(report['removed_field_paths'])}")
        except (OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
