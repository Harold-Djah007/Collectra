import uuid

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.decorators import no_conflict, require_can_edit_apps
from corehq.apps.app_manager.exceptions import ModuleNotFoundException
from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.views.apps import clear_app_cache
from corehq.apps.app_manager.xlsform import (
    MAX_XLSFORM_SIZE,
    XlsFormDefinition,
    XlsFormError,
    build_xform,
    parse_xlsform,
)
from corehq.apps.domain.decorators import domain_admin_required
from corehq.apps.hqwebapp.decorators import use_bootstrap5


XLSFORM_PREVIEW_TIMEOUT = 60 * 60
NEW_MODULE_VALUE = "__new__"


def _user_id(request):
    couch_user = getattr(request, "couch_user", None)
    return (
        getattr(couch_user, "get_id", None)
        or getattr(couch_user, "username", None)
        or request.user.get_username()
    )


def _preview_cache_key(token):
    return f"xlsform-preview:{token}"


def _module_options(app):
    if app is None:
        return []
    default_language = app.langs[0] if app.langs else "en"
    options = []
    for module in app.get_modules():
        if not hasattr(module, "new_form"):
            continue
        name = module.name.get(default_language) or next(iter(module.name.values()), _("Untitled Menu"))
        options.append({
            "unique_id": module.get_or_create_unique_id(),
            "name": name,
        })
    return options


def _preview_rows(definition):
    choices_by_list = {}
    for choice in definition.choices:
        choices_by_list.setdefault(choice.list_name, []).append(choice)
    return [
        {
            "question": row,
            "choices": choices_by_list.get(row.list_name, []),
        }
        for row in definition.rows
        if not row.kind.startswith("end_")
    ]


def _builder_context(domain, app=None, definition=None, preview_token=""):
    return {
        "domain": domain,
        "app": app,
        "definition": definition,
        "preview_token": preview_token,
        "preview_rows": _preview_rows(definition) if definition else [],
        "module_options": _module_options(app),
        "new_module_value": NEW_MODULE_VALUE,
        "max_upload_mb": MAX_XLSFORM_SIZE // (1024 * 1024),
    }


def _render_builder(request, domain, app=None, definition=None, preview_token=""):
    return render(
        request,
        "app_manager/excel_form_builder.html",
        _builder_context(domain, app, definition, preview_token),
    )


def _cache_definition(request, domain, app, definition):
    token = uuid.uuid4().hex
    cache.set(
        _preview_cache_key(token),
        {
            "domain": domain,
            "app_id": app.get_id if app else "",
            "user_id": _user_id(request),
            "definition": definition.to_dict(),
        },
        XLSFORM_PREVIEW_TIMEOUT,
    )
    return token


def _load_cached_definition(request, domain, app, token):
    payload = cache.get(_preview_cache_key(token))
    expected_app_id = app.get_id if app else ""
    if not payload or (
        payload.get("domain") != domain
        or payload.get("app_id") != expected_app_id
        or payload.get("user_id") != _user_id(request)
    ):
        raise XlsFormError(_("That preview expired or does not belong to this application."))
    return XlsFormDefinition.from_dict(payload["definition"])


def _validate_upload(upload):
    if not upload:
        raise XlsFormError(_("Choose a SurveyCTO/XLSForm workbook to upload."))
    if not upload.name.lower().endswith((".xlsx", ".xlsm")):
        raise XlsFormError(_("Upload an Excel workbook ending in .xlsx or .xlsm."))
    if upload.size > MAX_XLSFORM_SIZE:
        raise XlsFormError(
            _("The workbook is larger than the %(limit)d MB upload limit.")
            % {"limit": MAX_XLSFORM_SIZE // (1024 * 1024)}
        )


def _save_draft(request, domain, app, definition, token):
    language = definition.default_language or "en"
    if app is None:
        app_name = (request.POST.get("app_name") or "").strip() or definition.form_title
        app = Application.new_app(domain, app_name, lang=language)

    module_unique_id = request.POST.get("module_unique_id") or NEW_MODULE_VALUE
    if module_unique_id == NEW_MODULE_VALUE:
        module_name = (request.POST.get("module_name") or "").strip() or _("Imported Surveys")
        module = app.add_module(Module.new_module(module_name, language))
    else:
        try:
            module = app.get_module_by_unique_id(module_unique_id)
        except ModuleNotFoundException as exc:
            raise XlsFormError(str(exc)) from exc

    form_title = (request.POST.get("form_title") or "").strip() or definition.form_title
    form = module.new_form(form_title, language)
    form.source = build_xform(definition)

    for app_language in definition.languages:
        if app_language not in app.langs:
            app.langs.append(app_language)
    if getattr(request.project, "secure_submissions", False):
        app.secure_submissions = True

    app.save()
    cache.delete(_preview_cache_key(token))
    clear_app_cache(request, domain)
    messages.success(
        request,
        _("%(name)s was imported as a draft with %(count)d questions. Review it, then publish when ready.")
        % {"name": form_title, "count": definition.question_count},
    )
    return redirect("view_form", domain, app.get_id, form.get_unique_id())


def _xlsform_builder(request, domain, app=None):
    if request.method == "GET":
        return _render_builder(request, domain, app)

    action = request.POST.get("action", "validate")
    if action == "save":
        token = request.POST.get("preview_token", "")
        try:
            definition = _load_cached_definition(request, domain, app, token)
            return _save_draft(request, domain, app, definition, token)
        except XlsFormError as exc:
            messages.error(request, str(exc))
            definition = locals().get("definition")
            return _render_builder(request, domain, app, definition, token if definition else "")

    upload = request.FILES.get("spreadsheet")
    try:
        _validate_upload(upload)
        definition = parse_xlsform(upload, upload.name)
    except XlsFormError as exc:
        messages.error(request, str(exc))
        return _render_builder(request, domain, app)

    preview_token = ""
    if not definition.errors:
        preview_token = _cache_definition(request, domain, app, definition)
    return _render_builder(request, domain, app, definition, preview_token)


@use_bootstrap5
@domain_admin_required
def form_builder_choice(request, domain):
    return render(request, "app_manager/form_builder_choice.html", _builder_context(domain))


@use_bootstrap5
@domain_admin_required
@no_conflict
def excel_form_builder(request, domain):
    """Create a new application from a validated SurveyCTO/XLSForm workbook."""
    return _xlsform_builder(request, domain)


@use_bootstrap5
@require_can_edit_apps
@no_conflict
def xlsform_import(request, domain, app_id):
    """Import a validated SurveyCTO/XLSForm workbook into an existing app draft."""
    app = get_app(domain, app_id)
    return _xlsform_builder(request, domain, app)
