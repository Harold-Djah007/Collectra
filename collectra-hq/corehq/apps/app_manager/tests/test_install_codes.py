from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from corehq.apps.app_manager.models.applications import ApplicationBase
from corehq.apps.app_manager.models.install_codes import AppInstallCode


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
