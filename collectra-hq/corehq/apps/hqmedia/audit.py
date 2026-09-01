from collections import defaultdict
from io import BytesIO
from pathlib import PurePosixPath

from couchdbkit.exceptions import ResourceNotFound
from PIL import Image

from corehq.apps.hqmedia.models import CommCareImage, CommCareMultimedia


REPAIRABLE_IMAGE_SUFFIXES = {'.jpeg', '.jpg', '.png'}


def _reference_details(reference):
    return {
        'module': reference.get_module_name(),
        'module_id': reference.module_unique_id,
        'form': reference.get_form_name(),
        'form_id': reference.form_unique_id,
        'language': reference.app_lang,
        'is_menu_media': reference.is_menu_media,
        'media_type': reference.media_class.__name__,
    }


def _can_replace_with_menu_icon(path, references):
    return (
        PurePosixPath(path).suffix.lower() in REPAIRABLE_IMAGE_SUFFIXES
        and bool(references)
        and all(
            reference.is_menu_media and reference.media_class is CommCareImage
            for reference in references
        )
    )


def _load_media(map_item):
    try:
        media_class = CommCareMultimedia.get_doc_class(map_item.media_type)
    except KeyError as error:
        raise ValueError(
            f'Unknown multimedia type: {map_item.media_type}'
        ) from error
    return media_class.get(map_item.multimedia_id)


def _validate_mapping(map_item, references, media_loader):
    expected_types = {
        reference.media_class.__name__ for reference in references
    }
    if map_item.media_type not in expected_types:
        return 'wrong_media_type', (
            f'Mapping contains {map_item.media_type}; references expect '
            f'{", ".join(sorted(expected_types))}'
        )

    try:
        media = media_loader(map_item)
    except ResourceNotFound:
        return (
            'missing_document',
            f'Multimedia document {map_item.multimedia_id} was not found',
        )
    except ValueError as error:
        return 'invalid_media_type', str(error)
    except Exception as error:
        return 'unreadable_document', f'{type(error).__name__}: {error}'

    try:
        attachment_id = media.attachment_id
        if not attachment_id or attachment_id not in media.blobs:
            return (
                'missing_attachment_metadata',
                'Multimedia document has no usable attachment metadata',
            )
    except (AssertionError, KeyError, TypeError) as error:
        return (
            'invalid_attachment_metadata',
            f'{type(error).__name__}: {error}',
        )

    try:
        with media.fetch_attachment(attachment_id, stream=True) as stream:
            stream.read(1)
    except ResourceNotFound:
        return 'missing_blob', f'Blob {attachment_id} was not found'
    except Exception as error:
        return 'unreadable_blob', f'{type(error).__name__}: {error}'

    return None, None


def audit_app_multimedia(app, media_loader=None):
    """Return every broken multimedia path referenced by an app draft.

    A path is only marked as automatically repairable when every use is a
    module/form menu image. Replacing question media would change form meaning,
    so those paths are reported but never assigned a generic fallback.
    """
    media_loader = media_loader or _load_media
    references_by_path = defaultdict(list)
    for reference in app.all_media():
        if reference.path:
            references_by_path[reference.path].append(reference)

    issues = []
    multimedia_map = app.multimedia_map or {}
    for path, references in sorted(references_by_path.items()):
        map_item = multimedia_map.get(path)
        if map_item is None:
            status = 'missing_mapping'
            detail = 'Application has no multimedia mapping for this path'
        else:
            status, detail = _validate_mapping(
                map_item, references, media_loader
            )

        if status:
            issues.append(
                {
                    'path': path,
                    'status': status,
                    'detail': detail,
                    'repairable_menu_image': _can_replace_with_menu_icon(
                        path, references
                    ),
                    'references': [
                        _reference_details(reference)
                        for reference in references
                    ],
                }
            )

    return issues


def make_menu_fallback_image(source_data, requested_path):
    """Return valid image bytes and filename matching a referenced suffix."""
    suffix = PurePosixPath(requested_path).suffix.lower()
    if suffix not in REPAIRABLE_IMAGE_SUFFIXES:
        raise ValueError(
            f'Unsupported menu image extension: {suffix or "(none)"}'
        )

    with Image.open(BytesIO(source_data)) as image:
        output = BytesIO()
        if suffix in {'.jpg', '.jpeg'}:
            image = image.convert('RGBA')
            background = Image.new('RGB', image.size, '#f5fbfb')
            background.paste(image, mask=image.getchannel('A'))
            background.save(output, format='JPEG', quality=92, optimize=True)
            return output.getvalue(), 'collectra-menu-fallback.jpg'

        image.save(output, format='PNG', optimize=True)
        return output.getvalue(), 'collectra-menu-fallback.png'
