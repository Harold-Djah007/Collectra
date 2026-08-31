from django.http import Http404, HttpResponseRedirect

from corehq.apps.app_manager.models.install_codes import AppInstallCode


def app_install_code(request, code):
    try:
        mapping = AppInstallCode.objects.get(code=code)
    except AppInstallCode.DoesNotExist:
        raise Http404()
    return HttpResponseRedirect(mapping.target_url)
