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
        'when explicitly requested, repair broken menu images or clear broken '
        'optional menu narration.'
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
            '--clear-broken-menu-audio',
            action='store_true',
            help=(
                'Plan removal of unavailable optional module/form menu audio. '
                'Question audio is never changed. Does not write without --apply.'
            ),
        )
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Save planned repairs. Requires at least one repair option.',
        )

    def handle(
        self,
        domain,
        app_id=None,
        report=None,
        repair_menu_images=False,
        clear_broken_menu_audio=False,
        apply=False,
        **options,
    ):
        if apply and not (repair_menu_images or clear_broken_menu_audio):
            raise CommandError(
                '--apply requires --repair-menu-images or '
                '--clear-broken-menu-audio'
            )

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
        image_repairs_applied = []
        audio_references_cleared = []
        app_reports = []

        for app in apps:
            issues = audit_app_multimedia(app)
            repairable_images = [
                issue for issue in issues if issue['repairable_menu_image']
            ]
            clearable_audio = [
                issue for issue in issues if issue['clearable_menu_audio']
            ]
            app_changed = False

            if repair_menu_images and repairable_images:
                if fallback_source is None:
                    fallback_source = self._load_fallback_source()

                for issue in repairable_images:
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
                        image_repairs_applied.append(
                            {
                                'app_id': app._id,
                                'app_name': app.name,
                                'path': issue['path'],
                            }
                        )
                        app_changed = True

            if clear_broken_menu_audio and clearable_audio:
                for issue in clearable_audio:
                    issue['clear_planned'] = True
                    if apply:
                        cleared = self._clear_menu_audio_path(
                            app, issue['path']
                        )
                        if not cleared:
                            raise CommandError(
                                'Could not locate the menu audio field for '
                                f'{issue["path"]} in application {app._id}'
                            )
                        audio_references_cleared.append(
                            {
                                'app_id': app._id,
                                'app_name': app.name,
                                'path': issue['path'],
                                'references_cleared': cleared,
                            }
                        )
                        app_changed = True

            if apply and app_changed:
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
            'repairs_applied': image_repairs_applied,
            'menu_audio_cleared': audio_references_cleared,
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
        self.stdout.write(
            f'Menu images repaired:  {len(image_repairs_applied)}'
        )
        self.stdout.write(
            f'Menu audio paths cleared: {len(audio_references_cleared)}'
        )
        for status, count in result['remaining_issue_counts'].items():
            self.stdout.write(f'  - {status}: {count}')

        if not apply:
            planned_images = sum(
                issue['repairable_menu_image']
                for app_report in app_reports
                for issue in app_report['issues']
            )
            planned_audio = sum(
                issue['clearable_menu_audio']
                for app_report in app_reports
                for issue in app_report['issues']
            )
            if repair_menu_images or clear_broken_menu_audio:
                self.stdout.write('')
                self.stdout.write(
                    'Dry run only. Planned menu repairs: '
                    f'{planned_images if repair_menu_images else 0} image, '
                    f'{planned_audio if clear_broken_menu_audio else 0} audio.'
                )
                self.stdout.write('Re-run with --apply to save them.')
        elif image_repairs_applied or audio_references_cleared:
            self.stdout.write('')
            self.stdout.write(
                'Only broken menu media references were changed.'
            )
            self.stdout.write(
                'Forms, cases, submissions, sync endpoints, and question media were not changed.'
            )
            self.stdout.write(
                'Make and release a new application version before installing it on a phone.'
            )

    @staticmethod
    def _clear_menu_audio_path(app, path):
        cleared = 0
        for module in app.get_modules():
            menu_items = [module]
            case_list_form = getattr(module, 'case_list_form', None)
            if getattr(case_list_form, 'form_id', None):
                menu_items.append(case_list_form)
            if hasattr(module, 'case_list') and getattr(
                module.case_list, 'show', False
            ):
                menu_items.append(module.case_list)
            menu_items.extend(module.get_forms())

            for item in menu_items:
                for language, audio_path in list(
                    (getattr(item, 'media_audio', None) or {}).items()
                ):
                    if audio_path == path:
                        item.set_audio(language, None)
                        cleared += 1

        if cleared and app.multimedia_map:
            app.multimedia_map.pop(path, None)
        return cleared

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
