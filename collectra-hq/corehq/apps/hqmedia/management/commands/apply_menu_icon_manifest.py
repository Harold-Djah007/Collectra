"""Apply reviewed semantic menu icons to exact application multimedia paths."""

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.hqmedia.audit import make_menu_fallback_image
from corehq.apps.hqmedia.management.commands.audit_app_multimedia import (
    Command as AuditMultimediaCommand,
)
from corehq.apps.hqmedia.models import CommCareImage


MAX_ICON_BYTES = 5 * 1024 * 1024
MAX_ICON_DIMENSION = 2048

REQUIRED_MAPPING_FIELDS = {
    'app_id',
    'app_name',
    'item_type',
    'item_name',
    'target_path',
    'icon',
}


def load_and_validate_manifest(manifest_path, domain):
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not manifest_path.is_file():
        raise CommandError(f'Manifest was not found: {manifest_path}')

    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(f'Unable to read manifest: {error}') from error

    if not isinstance(manifest, dict):
        raise CommandError('Manifest root must be an object')

    if manifest.get('domain') != domain:
        raise CommandError(
            f'Manifest domain {manifest.get("domain")!r} does not match {domain!r}'
        )

    mappings = manifest.get('mappings')
    if not isinstance(mappings, list) or not mappings:
        raise CommandError('Manifest must contain a non-empty mappings list')
    mapping_count = manifest.get('mapping_count')
    if not isinstance(mapping_count, int) or isinstance(mapping_count, bool):
        raise CommandError('Manifest mapping_count must be an integer')
    if mapping_count != len(mappings):
        raise CommandError('Manifest mapping_count does not match mappings')

    root = manifest_path.parent
    validated = []
    seen = set()
    for index, mapping in enumerate(mappings, start=1):
        if not isinstance(mapping, dict):
            raise CommandError(f'Mapping {index} must be an object')
        missing = REQUIRED_MAPPING_FIELDS - mapping.keys()
        if missing:
            raise CommandError(
                f'Mapping {index} is missing: {", ".join(sorted(missing))}'
            )
        for field in REQUIRED_MAPPING_FIELDS:
            value = mapping[field]
            if not isinstance(value, str) or not value.strip():
                raise CommandError(
                    f'Mapping {index} field {field!r} must be a non-empty string'
                )
        if mapping['item_type'] not in {'module', 'form'}:
            raise CommandError(
                f'Mapping {index} has unsupported item_type '
                f'{mapping["item_type"]!r}'
            )
        if not mapping['target_path'].startswith(
            'jr://file/commcare/image/'
        ):
            raise CommandError(
                f'Mapping {index} is not a CommCare image path'
            )

        key = (mapping['app_id'], mapping['target_path'])
        if key in seen:
            raise CommandError(
                f'Duplicate app/path mapping: {mapping["app_id"]} '
                f'{mapping["target_path"]}'
            )
        seen.add(key)

        icon_path = (root / mapping['icon']).resolve()
        try:
            icon_path.relative_to(root)
        except ValueError as error:
            raise CommandError(
                f'Mapping {index} icon escapes the manifest directory'
            ) from error
        if not icon_path.is_file() or icon_path.suffix.lower() != '.png':
            raise CommandError(
                f'Mapping {index} icon is not a PNG file: {icon_path}'
            )
        try:
            icon_size = icon_path.stat().st_size
            if icon_size > MAX_ICON_BYTES:
                raise CommandError(
                    f'Mapping {index} icon exceeds {MAX_ICON_BYTES} bytes: '
                    f'{icon_path}'
                )
            with Image.open(icon_path) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as error:
            raise CommandError(
                f'Mapping {index} icon is not a valid PNG: {icon_path}'
            ) from error
        if image_format != 'PNG':
            raise CommandError(
                f'Mapping {index} icon content is not PNG: {icon_path}'
            )
        if not width or not height or max(width, height) > MAX_ICON_DIMENSION:
            raise CommandError(
                f'Mapping {index} icon dimensions must be between 1 and '
                f'{MAX_ICON_DIMENSION} pixels: {width}x{height}'
            )

        validated.append({**mapping, 'icon_path': icon_path})

    return manifest_path, manifest, validated


def validate_app_reference(app, mapping):
    references = [
        reference
        for reference in app.all_media()
        if reference.path == mapping['target_path']
    ]
    if not references:
        raise CommandError(
            f'{app.name}: path is no longer referenced: '
            f'{mapping["target_path"]}'
        )
    if not all(
        reference.is_menu_media and reference.media_class is CommCareImage
        for reference in references
    ):
        raise CommandError(
            f'{app.name}: path is not exclusively a menu image: '
            f'{mapping["target_path"]}'
        )


class Command(BaseCommand):
    help = (
        'Replace exact application menu-image mappings from a reviewed icon '
        'manifest. The command is a dry run unless --apply is supplied.'
    )

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('manifest')
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Save the validated menu-image mappings.',
        )
        parser.add_argument(
            '--report',
            help='Write a JSON plan or apply report to this path.',
        )

    def handle(self, domain, manifest, apply=False, report=None, **options):
        manifest_path, manifest_data, mappings = load_and_validate_manifest(
            manifest, domain
        )
        apps = {
            app._id: app
            for app in get_apps_in_domain(domain, include_remote=False)
        }

        plans = []
        for mapping in mappings:
            app = apps.get(mapping['app_id'])
            if app is None:
                raise CommandError(
                    f'Application draft was not found: {mapping["app_id"]}'
                )
            if app.name != mapping['app_name']:
                raise CommandError(
                    f'Application name changed for {app._id}: '
                    f'{mapping["app_name"]!r} -> {app.name!r}'
                )
            validate_app_reference(app, mapping)

            source_data = mapping['icon_path'].read_bytes()
            converted_data, filename = make_menu_fallback_image(
                source_data, mapping['target_path']
            )
            previous = (app.multimedia_map or {}).get(mapping['target_path'])
            plans.append(
                {
                    **mapping,
                    'app': app,
                    'source_data': source_data,
                    'converted_size': len(converted_data),
                    'converted_filename': filename,
                    'previous_multimedia_id': getattr(
                        previous, 'multimedia_id', None
                    ),
                    'previous_media_type': getattr(previous, 'media_type', None),
                }
            )

        applied = []
        if apply:
            media_cache = {}
            changed_apps = set()
            for plan in plans:
                suffix = Path(plan['target_path']).suffix.lower()
                cache_key = (str(plan['icon_path']), suffix)
                if cache_key not in media_cache:
                    media_cache[cache_key] = (
                        AuditMultimediaCommand._get_or_create_fallback_media(
                            domain,
                            plan['source_data'],
                            plan['target_path'],
                        )
                    )
                plan['app'].create_mapping(
                    media_cache[cache_key], plan['target_path'], save=False
                )
                changed_apps.add(plan['app_id'])
                applied.append(
                    {
                        'app_id': plan['app_id'],
                        'app_name': plan['app_name'],
                        'item_type': plan['item_type'],
                        'item_name': plan['item_name'],
                        'target_path': plan['target_path'],
                        'icon': plan['icon'],
                        'previous_multimedia_id': plan[
                            'previous_multimedia_id'
                        ],
                        'previous_media_type': plan['previous_media_type'],
                        'new_multimedia_id': media_cache[cache_key]._id,
                    }
                )

            for app_id in sorted(changed_apps):
                apps[app_id].save()

        result = {
            'domain': domain,
            'generated_at': timezone.now().isoformat(),
            'manifest': str(manifest_path),
            'manifest_generated_at': manifest_data.get('generated_at'),
            'mode': 'apply' if apply else 'dry-run',
            'planned_mappings': len(plans),
            'applied_mappings': len(applied),
            'apps': dict(sorted(Counter(
                plan['app_name'] for plan in plans
            ).items())),
            'changes': applied if apply else [
                {
                    'app_id': plan['app_id'],
                    'app_name': plan['app_name'],
                    'item_type': plan['item_type'],
                    'item_name': plan['item_name'],
                    'target_path': plan['target_path'],
                    'icon': plan['icon'],
                    'previous_multimedia_id': plan['previous_multimedia_id'],
                    'previous_media_type': plan['previous_media_type'],
                }
                for plan in plans
            ],
        }

        if report:
            report_path = Path(report).expanduser().resolve()
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(result, indent=2, sort_keys=True), encoding='utf-8'
            )
            self.stdout.write(f'Report: {report_path}')

        self.stdout.write('')
        self.stdout.write('Semantic menu image manifest')
        self.stdout.write(f'Domain:            {domain}')
        self.stdout.write(f'Mappings planned:  {len(plans)}')
        self.stdout.write(f'Mappings applied:  {len(applied)}')
        for app_name, count in result['apps'].items():
            self.stdout.write(f'  - {app_name}: {count}')
        self.stdout.write('')
        if apply:
            self.stdout.write(
                'Only the validated menu-image multimedia mappings were changed.'
            )
            self.stdout.write(
                'Make and release new application versions after visual review.'
            )
        else:
            self.stdout.write('Dry run only. Re-run with --apply to save.')
