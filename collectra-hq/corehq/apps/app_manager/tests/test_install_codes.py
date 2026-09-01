from unittest.mock import patch

from couchdbkit import ResourceNotFound
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from corehq.apps.app_manager.models.applications import ApplicationBase
from corehq.apps.app_manager.models.install_codes import AppInstallCode


class AppQrCodeTests(SimpleTestCase):
    def test_qr_cache_changes_when_public_profile_url_changes(self):
        app = ApplicationBase()
        app.domain = 'plant'
        app._id = 'app-id'

        with (
            patch(
                'corehq.apps.app_manager.models.applications.reverse',
                return_value='/a/plant/apps/download/app-id/odk/profile.ccpr',
            ),
            patch.object(
                ApplicationBase,
                'lazy_fetch_attachment',
                autospec=True,
                side_effect=ResourceNotFound,
            ) as fetch,
            patch.object(ApplicationBase, 'lazy_put_attachment', autospec=True),
            patch('corehq.apps.settings.views.get_qrcode', side_effect=lambda url: url.encode()) as get_qrcode,
        ):
            app.custom_base_url = 'https://first.collectra.test'
            first_qr = app.get_odk_qr_code()
            app.custom_base_url = 'https://second.collectra.test'
            second_qr = app.get_odk_qr_code()

        self.assertNotEqual(first_qr, second_qr)
        self.assertNotEqual(fetch.call_args_list[0].args[1], fetch.call_args_list[1].args[1])
        self.assertEqual(
            [call.args[0] for call in get_qrcode.call_args_list],
            [
                'https://first.collectra.test/a/plant/apps/download/app-id/odk/profile.ccpr',
                'https://second.collectra.test/a/plant/apps/download/app-id/odk/profile.ccpr',
            ],
        )

    def test_qr_cache_changes_for_build_profile_and_media(self):
        app = ApplicationBase()
        app.domain = 'plant'
        app._id = 'app-id'
        app.custom_base_url = 'https://hq.collectra.test'

        def reverse_url(view_name, args):
            return f'/a/{args[0]}/apps/download/{args[1]}/{view_name}'

        with (
            patch('corehq.apps.app_manager.models.applications.reverse', side_effect=reverse_url),
            patch.object(
                ApplicationBase,
                'lazy_fetch_attachment',
                autospec=True,
                side_effect=ResourceNotFound,
            ) as fetch,
            patch.object(ApplicationBase, 'lazy_put_attachment', autospec=True),
            patch('corehq.apps.settings.views.get_qrcode', side_effect=lambda url: url.encode()),
        ):
            app.get_odk_qr_code(build_profile_id='field')
            app.get_odk_qr_code(with_media=True, build_profile_id='field')
            app.get_odk_qr_code(build_profile_id='supervisor')

        cache_names = [call.args[1] for call in fetch.call_args_list]
        self.assertEqual(len(cache_names), len(set(cache_names)))


class AppInstallCodeTests(TestCase):
    def test_reuses_mapping_for_same_target(self):
        first = AppInstallCode.absolute_url_for(
            'plant',
            'https://example.test/a/plant/apps/download/abc/odk/profile.ccpr',
            'https://example.test',
        )
        second = AppInstallCode.absolute_url_for(
            'plant',
            'https://example.test/a/plant/apps/download/abc/odk/profile.ccpr',
            'https://example.test',
        )

        self.assertEqual(first, second)
        self.assertEqual(AppInstallCode.objects.filter(domain='plant').count(), 1)

    def test_redirects_code_to_profile_url(self):
        mapping = AppInstallCode.objects.create(
            domain='plant',
            code='abc2345',
            target_url='https://example.test/a/plant/apps/download/abc/odk/profile.ccpr',
        )

        response = self.client.get(reverse('app_install_code', args=[mapping.code]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], mapping.target_url)

    def test_unknown_code_returns_404(self):
        response = self.client.get(reverse('app_install_code', args=['missing']))
        self.assertEqual(response.status_code, 404)

    def test_rejects_unsafe_target_when_creating_code(self):
        unsafe_targets = [
            'javascript:alert(1)',
            '//attacker.example/profile.ccpr',
            'https://user:password@example.test/profile.ccpr',
            ' https://example.test/profile.ccpr',
            'https://example.test/profile.ccpr\n',
        ]

        for target_url in unsafe_targets:
            with self.subTest(target_url=target_url):
                with self.assertRaises(ValueError):
                    AppInstallCode.absolute_url_for(
                        'plant',
                        target_url,
                        'https://hq.collectra.test',
                    )

        self.assertFalse(AppInstallCode.objects.exists())

    def test_unsafe_existing_mapping_returns_404(self):
        mapping = AppInstallCode.objects.create(
            domain='plant',
            code='bad2345',
            target_url='javascript:alert(1)',
        )

        response = self.client.get(
            reverse('app_install_code', args=[mapping.code])
        )

        self.assertEqual(response.status_code, 404)

    def test_generate_shortened_url_falls_back_without_bitly(self):
        app = ApplicationBase()
        app.domain = 'plant'
        app._id = 'app-id'

        with (
            patch(
                'corehq.apps.app_manager.models.applications.reverse',
                return_value='/a/plant/apps/download/app-id/odk/profile.ccpr',
            ),
            patch('corehq.apps.app_manager.models.applications.bitly.shorten', return_value=None),
            patch.object(ApplicationBase, 'url_base', 'https://hq.collectra.test'),
        ):
            short_url = ApplicationBase.generate_shortened_url(app, 'download_odk_profile')

        self.assertTrue(short_url.startswith('https://hq.collectra.test/s/'))
        code = short_url.rstrip('/').rsplit('/', 1)[-1]
        self.assertTrue(AppInstallCode.objects.filter(code=code, domain='plant').exists())
