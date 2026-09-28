"""Mark a legacy reopening request handled after verifying an earlier case recovery."""

from django.core.cache import cache
from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.management.commands.inspect_safisana_reopen_case import (
    without_single_case_close,
)
from corehq.apps.dashboard.reopen_requests import request_from_form, validate_reopen_request
from corehq.form_processor.models import CommCareCase, XFormInstance


def verify_previous_reopening(request_form, case, closing_form):
    """Require explicit IDs and evidence that the original close was archived."""
    validate_reopen_request(request_form)
    request = request_from_form(request_form)
    if not request['name'] or request['name'].casefold() != case.name.casefold():
        raise ValueError('The worker request name must match the original case name')
    if (case.domain != 'safisana' or case.type != 'dryingbed' or case.deleted
            or case.closed or not case.opened_on or case.opened_on > request_form.received_on):
        raise ValueError('Expected the original, currently open Safisana drying-bed case')
    if closing_form.domain != 'safisana' or closing_form.state != XFormInstance.ARCHIVED:
        raise ValueError('The original closing submission must already be archived')
    xml = closing_form.get_xml()
    if not xml:
        raise ValueError('The archived closing submission XML is unavailable')
    without_single_case_close(xml, case.case_id)
    return request


class Command(BaseCommand):
    help = 'Review an already reopened Safisana case and reconcile its older pending request.'

    def add_arguments(self, parser):
        parser.add_argument('--request-id', required=True)
        parser.add_argument('--case-id', required=True)
        parser.add_argument('--closing-form-id', required=True)
        parser.add_argument('--supervisor-id', required=True)
        parser.add_argument('--apply', action='store_true')

    def handle(self, request_id, case_id, closing_form_id, supervisor_id, apply, **options):
        if any(not value or len(value) > 80 for value in
               (request_id, case_id, closing_form_id, supervisor_id)):
            raise CommandError('Provide valid request, case, closing form, and supervisor IDs')
        try:
            request_form = XFormInstance.objects.get_form(request_id, 'safisana')
            case = CommCareCase.objects.get_case(case_id, 'safisana')
            closing_form = XFormInstance.objects.get_form(closing_form_id, 'safisana')
            request = verify_previous_reopening(request_form, case, closing_form)
        except (ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Verified request {request_id}: {request['name']} ({request['bed']})")
        self.stdout.write(f'Open case: {case_id}; archived closing form: {closing_form_id}')
        if not apply:
            self.stdout.write('Preview only. Pass --apply to mark this request handled.')
            return
        request_form.archive(user_id=supervisor_id)
        cache.delete('collectra:reopen-requests:safisana:v1')
        self.stdout.write('Request marked handled. The original case and monitoring forms were unchanged.')
