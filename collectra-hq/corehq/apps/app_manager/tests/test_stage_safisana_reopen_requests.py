from lxml import etree

from corehq.apps.app_manager.management.commands.stage_safisana_reopen_requests import (
    NS, REQUEST_XMLNS, build_request_form,
)


def test_worker_request_never_changes_a_case():
    root = etree.fromstring(build_request_form())
    data = root.xpath('//x:model/x:instance/*', namespaces=NS)[0]
    assert etree.QName(data).namespace == REQUEST_XMLNS
    assert root.xpath('//x:bind[@nodeset="/data/bed_number"]', namespaces=NS)[0].get('required') == 'true()'
    assert root.xpath('//x:bind[@nodeset="/data/reason"]', namespaces=NS)[0].get('required') == 'true()'
    assert root.xpath('//x:bind[@nodeset="/data/batch_start_date"]', namespaces=NS)[0].get('required') is None
    assert len(root.xpath('//x:select1[@ref="/data/bed_number"]/x:item', namespaces=NS)) == 7
    assert not root.xpath('//*[local-name()="case"]')
