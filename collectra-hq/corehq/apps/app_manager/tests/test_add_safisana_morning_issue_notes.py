from unittest import TestCase

from lxml import etree

from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import (
    H, MORNING_STATUS_LABELS, NS, STATUS_VALUES, X, add_morning_issue_notes,
)


class MorningIssueNotesTest(TestCase):
    def test_each_explanation_is_conditional_and_preserves_existing_calculation(self):
        root = etree.Element(f'{{{H}}}html')
        model = etree.SubElement(etree.SubElement(root, f'{{{X}}}head'), f'{{{X}}}model')
        instance = etree.SubElement(model, f'{{{X}}}instance')
        data = etree.SubElement(instance, 'data')
        translation = etree.SubElement(etree.SubElement(model, f'{{{X}}}itext'),
                                       f'{{{X}}}translation', lang='en')
        body = etree.SubElement(root, f'{{{H}}}body')
        old = etree.SubElement(model, f'{{{X}}}bind', nodeset='/data/legacy',
                               calculate="if(/data/status = 'completed', 'yes', '')")
        for path in MORNING_STATUS_LABELS:
            group_name, status_name = path.split('/')[-2:]
            group = data.find(group_name)
            if group is None:
                group = etree.SubElement(data, group_name)
            etree.SubElement(group, status_name)
            etree.SubElement(model, f'{{{X}}}bind', nodeset=path, required='true()')
            select = etree.SubElement(body, f'{{{X}}}select1', ref=path)
            for value in STATUS_VALUES:
                item = etree.SubElement(select, f'{{{X}}}item')
                etree.SubElement(item, f'{{{X}}}value').text = value

        add_morning_issue_notes(root)
        self.assertEqual(old.get('calculate'), "if(/data/status = 'completed', 'yes', '')")
        self.assertEqual(len(root.xpath('//h:body//x:input', namespaces=NS)), 12)
        for path in MORNING_STATUS_LABELS:
            note_path = path.removesuffix('_status') + '_issue_note'
            bind = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=note_path)[0]
            self.assertEqual(bind.get('relevant'), f"{path} = 'needs_attention'")
            self.assertEqual(bind.get('required'), 'true()')
            select = root.xpath('//h:body//x:select1[@ref=$path]', namespaces=NS, path=path)[0]
            self.assertEqual(select.getnext().get('ref'), note_path)
        self.assertEqual(len(translation.xpath('./x:text', namespaces=NS)), 12)
        with self.assertRaises(ValueError):
            add_morning_issue_notes(root)
