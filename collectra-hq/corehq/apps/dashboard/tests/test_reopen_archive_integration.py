"""Exercise HQ's archive behavior against an isolated SQL test database."""

from uuid import uuid4
from unittest.mock import patch

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.dashboard.reopen_requests import closing_form_for_reopen
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.form_processor.utils.xform import FormSubmissionBuilder


DOMAIN = 'safisana'


@sharded
class ReopenArchiveIntegrationTest(TestCase):
    """Test only synthetic cases in Django's test database, never live Safisana data."""

    def setUp(self):
        super().setUp()
        # Archiving emits case signals; forwarding is outside the reopening
        # workflow and requires CouchDB domain views in this SQL-only test.
        self.enterContext(patch('corehq.motech.repeaters.signals.domain_can_forward',
                                return_value=False))

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super().tearDownClass()

    def submit(self, case_block, **properties):
        xml = FormSubmissionBuilder(
            form_id=uuid4().hex,
            case_blocks=[case_block],
            form_properties=properties,
        ).as_xml_string()
        # This test exercises SQL form/case processing. Restore cache sizing
        # and case usage metrics query unrelated CouchDB design views, which
        # are not installed in this isolated SQL test database.
        with patch('casexml.apps.phone.restore_caching.get_loadtest_factor_for_restore_cache_key',
                   return_value=1), patch('corehq.form_processor.submission_post.report_case_usage'):
            form = submit_form_locally(xml, DOMAIN).xform
        self.assertTrue(form.is_normal, form.problem)
        return form

    def create_case(self):
        case_id = uuid4().hex
        self.submit(CaseBlock(
            case_id=case_id, create=True, case_type='dryingbed',
            case_name='test-bed-1', owner_id='test-worker', user_id='test-worker',
        ))
        return case_id

    def test_archiving_dedicated_close_reopens_original_case_and_keeps_measurements(self):
        case_id = self.create_case()
        measurement = self.submit(CaseBlock(case_id=case_id, user_id='test-worker'), reading='47')
        closing = self.submit(CaseBlock(case_id=case_id, user_id='test-worker', close=True),
                              close_reason='Batch complete')
        case = CommCareCase.objects.get_case(case_id, DOMAIN)
        self.assertTrue(case.closed)
        self.assertEqual(closing_form_for_reopen(case).form_id, closing.form_id)

        closing.archive(user_id='test-supervisor')

        reopened = CommCareCase.objects.get_case(case_id, DOMAIN)
        self.assertFalse(reopened.closed)
        self.assertEqual(reopened.case_id, case_id)
        self.assertEqual(XFormInstance.objects.get_form(measurement.form_id, DOMAIN).form_data['reading'], '47')
        self.assertTrue(XFormInstance.objects.get_form(measurement.form_id, DOMAIN).is_normal)
        self.assertTrue(XFormInstance.objects.get_form(closing.form_id, DOMAIN).is_archived)

    def test_archiving_combined_monitoring_close_also_archives_its_reading(self):
        case_id = self.create_case()
        combined = self.submit(CaseBlock(case_id=case_id, user_id='test-worker', close=True), reading='52')
        combined.archive(user_id='test-supervisor')

        self.assertFalse(CommCareCase.objects.get_case(case_id, DOMAIN).closed)
        self.assertTrue(XFormInstance.objects.get_form(combined.form_id, DOMAIN).is_archived)
