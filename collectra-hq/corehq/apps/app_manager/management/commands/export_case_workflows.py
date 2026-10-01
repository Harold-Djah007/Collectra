"""Export app case actions and form XML for a read-only compatibility review."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain


def _condition(action):
    condition = getattr(action, 'condition', None)
    return {
        'type': getattr(condition, 'type', None),
        'question': getattr(condition, 'question', None),
        'answer': getattr(condition, 'answer', None),
        'operator': getattr(condition, 'operator', None),
    }


def _updates(action):
    return {
        name: update.question_path
        for name, update in getattr(action, 'update', {}).items()
    }


def form_record(app, module, form, include_source=False):
    actions = getattr(form, 'actions', None)
    opening = getattr(actions, 'open_case', None)
    updating = getattr(actions, 'update_case', None)
    closing = getattr(actions, 'close_case', None)
    record = {
        'app_id': app._id,
        'app_name': app.name,
        'module_id': module.unique_id,
        'module_name': module.default_name(),
        'case_type': getattr(module, 'case_type', None),
        'form_id': form.unique_id,
        'form_name': form.default_name(),
        'open_case': {
            'condition': _condition(opening),
            'name_question': getattr(getattr(opening, 'name_update', None), 'question_path', None),
            'external_id_question': getattr(opening, 'external_id', None),
        },
        'update_case': {
            'condition': _condition(updating),
            'name_question': getattr(getattr(updating, 'name_update', None), 'question_path', None),
            'properties': _updates(updating),
        },
        'close_case': {'condition': _condition(closing)},
    }
    if include_source:
        source = form.source
        record['xml'] = source.decode('utf-8') if isinstance(source, bytes) else source
    return record


class Command(BaseCommand):
    help = 'Export live application form XML and case action mappings without changing application data.'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--output', required=True)
        parser.add_argument('--app-id', action='append', dest='app_ids')
        parser.add_argument('--include-source', action='store_true')

    def handle(self, domain, output, app_ids=None, include_source=False, **options):
        requested = set(app_ids or [])
        records = [
            form_record(app, module, form, include_source)
            for app in get_apps_in_domain(domain, include_remote=False)
            if not requested or app._id in requested
            for module in app.get_modules()
            for form in module.get_forms()
        ]
        path = Path(output).expanduser()
        path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(f'Exported {len(records)} form configurations to {path}')
