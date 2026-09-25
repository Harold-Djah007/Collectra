"""Inspect a closing submission before considering a case reopening."""

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.form_processor.exceptions import CaseNotFound, MissingFormXml
from corehq.form_processor.models import CommCareCase


CASE_XMLNS = 'http://commcarehq.org/case/transaction/v2'


def without_single_case_close(xml, case_id):
    root = etree.fromstring(xml)
    blocks = root.xpath('//*[local-name()="case" and namespace-uri()=$ns]', ns=CASE_XMLNS)
    if len(blocks) != 1 or blocks[0].get('case_id') != case_id:
        raise ValueError('The closing form must contain exactly one case block for this case')
    closes = blocks[0].xpath('./*[local-name()="close" and namespace-uri()=$ns]', ns=CASE_XMLNS)
    if len(closes) != 1:
        raise ValueError('Expected one explicit case-close action')
    blocks[0].remove(closes[0])
    return etree.tostring(root, encoding='UTF-8', xml_declaration=True)


class Command(BaseCommand):
    help = 'Write a read-only review of a Safisana drying-bed closing form.'

    def add_arguments(self, parser):
        parser.add_argument('case_id')
        parser.add_argument('--output-dir', required=True)

    def handle(self, case_id, output_dir, **options):
        try:
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', case_id):
                raise ValueError('Invalid case ID')
            case = CommCareCase.objects.get_case(case_id, 'safisana')
            if case.type != 'dryingbed' or not case.closed:
                raise ValueError('Expected a closed Safisana drying-bed case')
            closings = [tx for tx in case.get_closing_transactions() if not tx.revoked]
            if len(closings) != 1:
                raise ValueError('Expected exactly one active closing transaction')
            form = closings[0].form
            original = form.get_xml()
            if not original:
                raise ValueError('The closing form XML is unavailable')
            revised = without_single_case_close(original, case.case_id)
            directory = Path(output_dir).expanduser()
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f'{case_id}-closing-original.xml').write_bytes(original)
            (directory / f'{case_id}-closing-review.xml').write_bytes(revised)
            (directory / f'{case_id}-reopen-review.json').write_text(json.dumps({
                'case_id': case.case_id,
                'case_name': case.name,
                'closing_form_id': form.form_id,
                'closing_form_xmlns': form.xmlns,
                'review_only': True,
                'warning': 'No case was reopened. Editing a closing form requires a full '
                           'submission and reporting regression test before approval can apply it.',
            }, indent=2), encoding='utf-8')
            self.stdout.write(f'Wrote read-only case review to {directory}')
        except (CaseNotFound, MissingFormXml, OSError, ValueError, etree.XMLSyntaxError) as error:
            raise CommandError(str(error)) from error
