from django.test import RequestFactory, SimpleTestCase

from corehq.apps.cloudcare.views import FormplayerMain
from corehq.apps.public_webforms.models import (
    PublicFormSession,
    PublicFormUser,
    PublicWebform,
)


class GetRestoreAsUserTests(SimpleTestCase):

    def _public_form_request(self):
        webform = PublicWebform(domain='public-forms-domain')
        session = PublicFormSession(public_webform=webform)
        request = RequestFactory().get('/')
        request.couch_user = PublicFormUser(session)
        return request

    def test_public_form_session_returns_itself(self):
        request = self._public_form_request()
        user, set_cookie = FormplayerMain.get_restore_as_user(request, 'public-forms-domain')
        assert user is request.couch_user

    def test_public_form_session_set_cookie_is_noop(self):
        request = self._public_form_request()
        _, set_cookie = FormplayerMain.get_restore_as_user(request, 'public-forms-domain')
        response = object()
        assert set_cookie(response) is response


class CollectraWebAppsVisibilityTests(SimpleTestCase):
    def test_disabled_web_apps_tab_is_hidden(self):
        from django.test import override_settings
        from corehq.tabs.tabclasses import CloudcareTab
        with override_settings(COLLECTRA_WEB_APPS_ENABLED=False):
            tab = object.__new__(CloudcareTab)
            assert not tab._is_viewable

    def test_disabled_web_apps_redirects_to_dashboard(self):
        from django.test import override_settings
        from django.urls import reverse
        with override_settings(COLLECTRA_WEB_APPS_ENABLED=False):
            response = FormplayerMain().get(RequestFactory().get('/'), 'safisana')
        assert response.status_code == 302
        assert response.url == reverse('dashboard_domain', args=['safisana'])

    def test_form_builder_preview_keeps_its_own_view(self):
        from django.urls import resolve, reverse
        from corehq.apps.cloudcare.views import PreviewAppView
        match = resolve(reverse('preview_app', args=['safisana', 'test-app']))
        assert match.func.view_class is PreviewAppView
