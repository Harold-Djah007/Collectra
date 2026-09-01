import json
from collections import Counter
from pathlib import Path

from couchdbkit.exceptions import ResourceNotFound
from django.contrib.staticfiles import finders
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.hqmedia.audit import (
    audit_app_multimedia,
    make_menu_fallback_image,
)
from corehq.apps.hqmedia.models import CommCareImage


FALLBACK_ICON = 'hqwebapp/images/collectra-icon.png'


class Command(BaseCommand):
    help = (
        'Audit all multimedia referenced by application drafts in a domain and, '
        'when explicitly requested, replace only broken menu images with a Collectra fallback.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument(
            '--app-id', help='Limit the audit to one application draft ID.'
        )
        parser.add_argument(
            '--report', help='Write the complete JSON report to this path.'
        )
        parser.add_argument(
            '--repair-menu-images',
            action='store_true',
            help='Plan replacement of broken module/form menu images. Does not write without --apply.',
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Save planned menu-image replacements. Requires --repair-menu-images.',
        )

    def handle(
        self,
        domain,
        app_id=None,
        report=None,
        repair_menu_images=False,
        apply=False,
        **options,
    ):
        if apply and not repair_menu_images:
            raise CommandError('--apply requires --repair-menu-images')

        apps = sorted(
            get_apps_in_domain(domain, include_remote=False),
            key=lambda app: (app.name.lower(), app._id),
        )
        if app_id:
            apps = [app for app in apps if app._id == app_id]
            if not apps:
                raise CommandError(
                    f'Application draft {app_id} was not found in domain {domain}'
                )

        fallback_source = None
        fallback_media = {}
        repairs_applied = []
        app_reports = []

        for app in apps:
            issues = audit_app_multimedia(app)
            repairable = [
                issue for issue in issues if issue['repairable_menu_image']
            ]

            if repair_menu_images and repairable:
                if fallback_source is None:
                    fallback_source = self._load_fallback_source()

                for issue in repairable:
                    issue['repair_planned'] = True
                    if apply:
                        suffix = Path(issue['path']).suffix.lower()
                        if suffix not in fallback_media:
                            fallback_media[suffix] = (
                                self._get_or_create_fallback_media(
                                    domain,
                                    fallback_source,
                                    issue['path'],
                                )
                            )
                        app.create_mapping(
                            fallback_media[suffix], issue['path'], save=False
                        )
                        repairs_applied.append(
                            {
                                'app_id': app._id,
                                'app_name': app.name,
                                'path': issue['path'],
                            }
                        )

                if apply:
                    app.save()
                    issues = audit_app_multimedia(app)

            app_reports.append(
                {
                    'app_id': app._id,
                    'app_name': app.name,
                    'issues': issues,
                }
            )

        remaining_issues = [
            issue
            for app_report in app_reports
            for issue in app_report['issues']
        ]
        issue_counts = Counter(issue['status'] for issue in remaining_issues)
        result = {
            'domain': domain,
            'generated_at': timezone.now().isoformat(),
            'mode': 'apply' if apply else 'dry-run',
            'apps_scanned': len(app_reports),
            'apps_with_issues': sum(
                bool(item['issues']) for item in app_reports
            ),
            'remaining_issues': len(remaining_issues),
            'remaining_issue_counts': dict(sorted(issue_counts.items())),
            'repairs_applied': repairs_applied,
            'applications': app_reports,
        }

        if report:
            report_path = Path(report).expanduser().resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding='utf-8'
            )
            self.stdout.write(f'Report: {report_path}')

        self.stdout.write('')
        self.stdout.write('Application multimedia audit')
        self.stdout.write(f'Domain:                {domain}')
        self.stdout.write(f'Applications scanned:  {result["apps_scanned"]}')
        self.stdout.write(
            f'Apps with issues:      {result["apps_with_issues"]}'
        )
        self.stdout.write(
            f'Remaining issues:      {result["remaining_issues"]}'
        )
        self.stdout.write(f'Menu images repaired:  {len(repairs_applied)}')
        for status, count in result['remaining_issue_counts'].items():
            self.stdout.write(f'  - {status}: {count}')

        if repair_menu_images and not apply:
            planned = sum(
                issue['repairable_menu_image']
                for app_report in app_reports
                for issue in app_report['issues']
            )
            self.stdout.write('')
            self.stdout.write(
                f'Dry run only. Menu image replacements planned: {planned}'
            )
            self.stdout.write(
                'Re-run with --repair-menu-images --apply to save them.'
            )
        elif apply:
            self.stdout.write('')
            self.stdout.write('Only broken menu image mappings were changed.')
            self.stdout.write(
                'Forms, cases, submissions, sync endpoints, and question media were not changed.'
            )
            self.stdout.write(
                'Make and release a new application version before installing it on a phone.'
            )

    @staticmethod
    def _load_fallback_source():
        path = finders.find(FALLBACK_ICON)
        if not path:
            raise CommandError(
                f'Collectra fallback icon was not found: {FALLBACK_ICON}'
            )
        return Path(path).read_bytes()

    @staticmethod
    def _get_or_create_fallback_media(domain, source_data, requested_path):
        data, filename = make_menu_fallback_image(source_data, requested_path)
        multimedia = CommCareImage.get_by_data(data)

        if getattr(multimedia, '_id', None):
            try:
                attachment_id = multimedia.attachment_id
                if not attachment_id:
                    raise ResourceNotFound('missing attachment id')
                with multimedia.fetch_attachment(
                    attachment_id, stream=True
                ) as stream:
                    stream.read(1)
            except (ResourceNotFound, AssertionError, KeyError):
                multimedia = CommCareImage(
                    file_hash=CommCareImage.generate_hash(data)
                )

        if not getattr(multimedia, '_id', None):
            multimedia.attach_data(
                data,
                original_filename=filename,
                username='collectra-migration-repair',
            )

        if domain not in multimedia.valid_domains:
            multimedia.add_domain(domain, owner=True)
        return multimedia
