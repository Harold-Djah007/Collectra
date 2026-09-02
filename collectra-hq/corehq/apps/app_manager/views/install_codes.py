from django.http import Http404, HttpResponseRedirect

from corehq.apps.app_manager.models.install_codes import (
    AppInstallCode,
    validate_target_url,
)


def app_install_code(request, code):
    try:
        mapping = AppInstallCode.objects.get(code=code)
    except AppInstallCode.DoesNotExist:
        raise Http404()
    try:
        target_url = validate_target_url(mapping.target_url)
    except ValueError:
        raise Http404()
    return HttpResponseRedirect(target_url)
