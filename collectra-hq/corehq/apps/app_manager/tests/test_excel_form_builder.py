from django.test import SimpleTestCase

from corehq.apps.app_manager.views.form_builder import (
    _build_xform,
    _headers_from_first_row,
    _safe_xml_name,
)


class ExcelFormBuilderHelpersTest(SimpleTestCase):
    def test_safe_xml_name_strips_punctuation(self):
        self.assertEqual(_safe_xml_name('First Name?', 1), 'first_name')

    def test_safe_xml_name_prefixes_numeric(self):
        self.assertEqual(_safe_xml_name('1age', 2), 'question_2')

    def test_headers_from_first_row_skips_blanks(self):
        self.assertEqual(
            _headers_from_first_row(('Name', None, ' Age ', '')),
            ['Name', 'Age'],
        )

    def test_headers_from_empty_row(self):
        self.assertEqual(_headers_from_first_row(None), [])
        self.assertEqual(_headers_from_first_row(()), [])

    def test_build_xform_escapes_labels(self):
        xml = _build_xform('Survey <1>', ['A & B'])
        self.assertIn('<h:title>Survey &lt;1&gt;</h:title>', xml)
        self.assertIn('<label>A &amp; B</label>', xml)
        self.assertIn('<a_b />', xml)
