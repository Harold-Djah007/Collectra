"""Export every module and form menu-image slot for reviewed icon design."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from redis.exceptions import ConnectionError as RedisConnectionError

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain


def localized_values(value):
    if value is None:
        return {}
    if isinstance(value, str):
        return {'default': value}
    try:
        items = value.items()
    except AttributeError:
        return {'default': str(value)}
    return {
        str(language): content
        for language, content in items
    }


def serialize_form(form, index):
    return {
        'index': index,
        'id': getattr(form, 'unique_id', None),
        'name': localized_values(getattr(form, 'name', None)),
        'media_image': localized_values(
            getattr(form, 'media_image', None)
        ),
    }


def serialize_module(module, index):
    return {
        'index': index,
        'id': getattr(module, 'unique_id', None),
        'name': localized_values(getattr(module, 'name', None)),
        'media_image': localized_values(
            getattr(module, 'media_image', None)
        ),
        'forms': [
            serialize_form(form, form_index)
            for form_index, form in enumerate(getattr(module, 'forms', ()))
        ],
    }


def build_inventory(domain):
    apps = sorted(
        get_apps_in_domain(domain, include_remote=False),
        key=lambda app: (app.name.casefold(), app._id),
    )
    applications = [
        {
            'app_id': app._id,
            'app_name': app.name,
            'languages': list(getattr(app, 'langs', ()) or ()),
            'modules': [
                serialize_module(module, module_index)
                for module_index, module in enumerate(
                    getattr(app, 'modules', ())
                )
            ],
        }
        for app in apps
    ]
    return {
        'domain': domain,
        'generated_at': timezone.now().isoformat(),
        'application_count': len(applications),
        'module_count': sum(
            len(app['modules']) for app in applications
        ),
        'form_count': sum(
            len(module['forms'])
            for app in applications
            for module in app['modules']
        ),
        'applications': applications,
    }


class Command(BaseCommand):
    help = (
        'Export every application draft, module, form, and current menu-image '
        'slot in a domain. This command never changes application data.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--report',
            required=True,
            help='Write the complete JSON inventory to this path.',
        )

    def handle(self, domain, report, **options):
        if not domain.strip():
            raise CommandError('Domain must not be empty')

        try:
            result = build_inventory(domain)
        except RedisConnectionError as error:
            raise CommandError(
                'Redis is unavailable. Start the local HQ services with '
                '`./scripts/docker up -d redis couch`, wait until they are '
                'healthy, and run this command again.'
            ) from error
        report_path = Path(report).expanduser().resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(result, indent=2, sort_keys=True),
            encoding='utf-8',
        )

        self.stdout.write(f'Report: {report_path}')
        self.stdout.write('')
        self.stdout.write('Complete menu icon inventory')
        self.stdout.write(f'Domain:       {domain}')
        self.stdout.write(
            f'Applications: {result["application_count"]}'
        )
        self.stdout.write(f'Modules:      {result["module_count"]}')
        self.stdout.write(f'Forms:        {result["form_count"]}')
        self.stdout.write('')
        self.stdout.write('No application data was changed.')
