"""Keep measurements and existing calculated questions when moving the close action."""

import pytest
from django.test import SimpleTestCase
from lxml import etree

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.management.commands.stage_safisana_close_only import (
    XMLNS, build_close_form, change_monitoring_source,
)


X = {'x': 'http://www.w3.org/2002/xforms', 'h': 'http://www.w3.org/1999/xhtml'}


def test_dedicated_close_form_has_no_monitoring_readings_or_case_id_field():
    root = etree.fromstring(build_close_form())
    data = root.xpath('//x:model/x:instance/*', namespaces=X)[0]
    assert etree.QName(data).namespace == XMLNS
    assert [etree.QName(node).localname for node in data] == ['notice', 'confirm_close', 'reason']
    assert root.xpath('//x:bind[@nodeset="/data/confirm_close"]', namespaces=X)[0].get('constraint') == (
        ". = 'yes'")
    assert root.xpath('//x:bind[@nodeset="/data/reason"]', namespaces=X)[0].get('required') == 'true()'
    assert not root.xpath('//*[local-name()="case"]')


MONITORING = '''<h:html xmlns:h="http://www.w3.org/1999/xhtml"
    xmlns="http://www.w3.org/2002/xforms" xmlns:xsd="http://www.w3.org/2001/XMLSchema">
  <h:head><model>
    <instance><data xmlns="urn:drying-bed"><height/><close_batch/><close><thickness/></close></data></instance>
    <bind nodeset="/data/height" calculate="10 + 5"/>
    <bind nodeset="/data/close" relevant="/data/close_batch = 'yes'"/>
    <itext><translation lang="en">
      <text id="close_batch-label"><value>Close batch</value></text>
      <text id="close_batch-yes-label"><value>Yes</value></text>
      <text id="close_batch-no-label"><value>No</value></text>
    </translation></itext>
  </model></h:head>
  <h:body><select1 ref="/data/close_batch">
    <item><label>No</label><value>no</value></item>
    <item><label>Yes</label><value>yes</value></item>
  </select1></h:body>
</h:html>'''


def test_monitoring_keeps_fields_conditions_and_calculations():
    before = etree.fromstring(MONITORING.encode())
    after = etree.fromstring(change_monitoring_source(MONITORING))
    for path in ('/data/height', '/data/close_batch', '/data/close/thickness'):
        assert len(after.xpath(f'//*[local-name()="data"]//*[local-name()="{path.split("/")[-1]}"]')) == 1
    assert before.xpath('//x:bind[@calculate]/@calculate', namespaces=X) == after.xpath(
        '//x:bind[@calculate]/@calculate', namespaces=X)
    assert before.xpath('//x:bind[@relevant]/@relevant', namespaces=X) == after.xpath(
        '//x:bind[@relevant]/@relevant', namespaces=X)
    assert 'case will stay open' in after.xpath(
        '//x:text[@id="close_batch-label"]/x:value/text()', namespaces=X)[0]


def test_unexpected_choice_values_are_rejected():
    with pytest.raises(ValueError):
        change_monitoring_source(MONITORING.replace('<value>yes</value>', '<value>unknown</value>'))


class CloseOnlyCaseActionTest(SimpleTestCase):
    def test_rendered_form_closes_existing_drying_bed_without_measurements(self):
        app = Application.new_app('safisana', 'Test Close Only')
        app.version = 3
        module = app.add_module(Module.new_module('Drying Bed', 'en'))
        module.case_type = 'dryingbed'
        form = app.new_form(module.id, 'Close drying-bed batch', 'en',
                            attachment=build_close_form().decode('utf-8'))
        form.requires = 'case'
        form.actions.close_case.condition.type = 'always'
        rendered = form.render_xform()
        root = etree.fromstring(rendered.encode('utf-8') if isinstance(rendered, str) else rendered)
        assert root.xpath('//*[local-name()="case"]/*[local-name()="close"]')
        assert not root.xpath('//*[local-name()="reading" or local-name()="height"]')
