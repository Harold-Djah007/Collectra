from unittest import TestCase

from lxml import etree

from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import (
    MORNING_STATUS_LABELS, NS, X, refine_staged_morning_choices,
)


class RefineMorningChoicesTest(TestCase):
    def test_three_contextual_values_without_touching_calculations(self):
        root = etree.Element('{http://www.w3.org/1999/xhtml}html')
        model = etree.SubElement(etree.SubElement(root, f'{{{X}}}head'), f'{{{X}}}model')
        bind = etree.SubElement(model, f'{{{X}}}bind', nodeset='/data/legacy',
                                calculate="if(/data/status = 'completed', 'yes', '')")
        itext = etree.SubElement(model, f'{{{X}}}itext')
        etree.SubElement(itext, f'{{{X}}}translation', lang='en')
        body = etree.SubElement(root, '{http://www.w3.org/1999/xhtml}body')
        for path in MORNING_STATUS_LABELS:
            select = etree.SubElement(body, f'{{{X}}}select1', ref=path)
            for status in ('completed', 'needs_attention', 'not_completed', 'not_applicable'):
                item = etree.SubElement(select, f'{{{X}}}item')
                etree.SubElement(item, f'{{{X}}}label', ref="jr:itext('generic')")
                etree.SubElement(item, f'{{{X}}}value').text = status

        original_calculation = bind.get('calculate')
        refine_staged_morning_choices(root)
        self.assertEqual(bind.get('calculate'), original_calculation)
        labels = []
        for path in MORNING_STATUS_LABELS:
            options = root.xpath('//x:select1[@ref=$path]/x:item', namespaces=NS, path=path)
            self.assertEqual([item.find(f'{{{X}}}value').text for item in options],
                             ['completed', 'needs_attention', 'not_completed'])
            labels.append(options[0].find(f'{{{X}}}label').get('ref'))
        self.assertEqual(len(set(labels)), 12)
