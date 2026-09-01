from contextlib import contextmanager
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import patch

from couchdbkit.exceptions import ResourceNotFound
from django.core.management.base import CommandError
from django.test import SimpleTestCase
from PIL import Image

from corehq.apps.hqmedia.audit import (
    audit_app_multimedia,
    make_menu_fallback_image,
)
from corehq.apps.hqmedia.management.commands.audit_app_multimedia import (
    Command,
)
from corehq.apps.hqmedia.models import ApplicationMediaReference, CommCareImage


class FakeApp:
    def __init__(self, references, multimedia_map=None):
        self._references = references
        self.multimedia_map = multimedia_map or {}

    def all_media(self):
        return self._references


class FakeMedia:
    attachment_id = 'blob-id'
    blobs = {'blob-id': object()}

    @contextmanager
    def fetch_attachment(self, attachment_id, stream=False):
        assert attachment_id == self.attachment_id
        assert stream
        yield SimpleNamespace(read=lambda size: b'x'[:size])


def image_reference(path, is_menu_media=True):
    return ApplicationMediaReference(
        path,
        module_name={'en': 'Module'},
        form_name={'en': 'Form'},
        media_class=CommCareImage,
        is_menu_media=is_menu_media,
    )


class ApplicationMultimediaAuditTest(SimpleTestCase):
    def test_valid_mapping_has_no_issues(self):
        path = 'jr://file/commcare/image/module0_en.png'
        mapping = SimpleNamespace(
            media_type='CommCareImage', multimedia_id='media-id'
        )
        app = FakeApp([image_reference(path)], {path: mapping})

        self.assertEqual(
            audit_app_multimedia(app, media_loader=lambda item: FakeMedia()),
            [],
        )

    def test_missing_menu_mapping_is_repairable(self):
        path = 'jr://file/commcare/image/module0_en.png'
        issues = audit_app_multimedia(FakeApp([image_reference(path)]))

        self.assertEqual(issues[0]['status'], 'missing_mapping')
        self.assertTrue(issues[0]['repairable_menu_image'])

    def test_question_media_is_never_automatically_replaced(self):
        path = 'jr://file/commcare/image/question.jpg'
        issues = audit_app_multimedia(
            FakeApp([image_reference(path, is_menu_media=False)])
        )

        self.assertFalse(issues[0]['repairable_menu_image'])

    def test_shared_menu_and_question_path_is_not_replaced(self):
        path = 'jr://file/commcare/image/shared.jpg'
        app = FakeApp(
            [
                image_reference(path),
                image_reference(path, is_menu_media=False),
            ]
        )

        self.assertFalse(audit_app_multimedia(app)[0]['repairable_menu_image'])

    def test_missing_media_document_is_reported(self):
        path = 'jr://file/commcare/image/module10_form0_en.jpg'
        mapping = SimpleNamespace(
            media_type='CommCareImage', multimedia_id='missing'
        )
        app = FakeApp([image_reference(path)], {path: mapping})

        def missing_media(map_item):
            raise ResourceNotFound(map_item.multimedia_id)

        issues = audit_app_multimedia(app, media_loader=missing_media)
        self.assertEqual(issues[0]['status'], 'missing_document')
        self.assertTrue(issues[0]['repairable_menu_image'])


class MenuFallbackImageTest(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = Image.new('RGBA', (32, 32), (0, 171, 158, 160))
        output = BytesIO()
        source.save(output, format='PNG')
        cls.source_data = output.getvalue()

    def test_png_fallback_is_valid_png(self):
        data, filename = make_menu_fallback_image(
            self.source_data, 'module0_en.png'
        )
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.format, 'PNG')
        self.assertTrue(filename.endswith('.png'))

    def test_jpg_fallback_is_valid_jpeg(self):
        data, filename = make_menu_fallback_image(
            self.source_data, 'module10_form0_en.jpg'
        )
        with Image.open(BytesIO(data)) as image:
            self.assertEqual(image.format, 'JPEG')
        self.assertTrue(filename.endswith('.jpg'))


class AuditCommandTest(SimpleTestCase):
    def test_apply_requires_repair_flag(self):
        with self.assertRaises(CommandError):
            Command().handle(domain='safisana', apply=True)

    @patch.object(Command, '_load_fallback_source', return_value=b'icon')
    @patch.object(Command, '_get_or_create_fallback_media')
    @patch(
        'corehq.apps.hqmedia.management.commands.audit_app_multimedia.audit_app_multimedia'
    )
    @patch(
        'corehq.apps.hqmedia.management.commands.audit_app_multimedia.get_apps_in_domain'
    )
    def test_apply_replaces_and_saves_menu_mapping(
        self,
        get_apps_in_domain,
        audit_multimedia,
        get_fallback_media,
        load_fallback_source,
    ):
        path = 'jr://file/commcare/image/module10_form0_en.jpg'
        app = SimpleNamespace(
            _id='app-id',
            name='Processing - Plant',
            create_mapping=lambda media, mapped_path, save: mappings.append(
                (media, mapped_path, save)
            ),
            save=lambda: saves.append(True),
        )
        fallback_media = object()
        mappings = []
        saves = []
        get_apps_in_domain.return_value = [app]
        get_fallback_media.return_value = fallback_media
        audit_multimedia.side_effect = [
            [
                {
                    'path': path,
                    'status': 'missing_mapping',
                    'repairable_menu_image': True,
                    'references': [],
                }
            ],
            [],
        ]

        Command().handle(
            domain='safisana', repair_menu_images=True, apply=True
        )

        self.assertEqual(mappings, [(fallback_media, path, False)])
        self.assertEqual(saves, [True])
        load_fallback_source.assert_called_once_with()
