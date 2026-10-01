import pytest
from lxml import etree

from corehq.apps.app_manager.management.commands.inspect_safisana_reopen_case import (
    CASE_XMLNS, without_single_case_close,
)


def test_dry_bed_measurement_survives_close_action_review():
    source = (f'<data><measurement>47</measurement>'
              f'<case xmlns="{CASE_XMLNS}" case_id="original-case">'
              '<update><reading>47</reading></update><close/></case></data>').encode()
    root = etree.fromstring(without_single_case_close(source, 'original-case'))
    assert root.findtext('measurement') == '47'
    assert root.xpath('//*[local-name()="reading"]/text()') == ['47']
    assert not root.xpath('//*[local-name()="close"]')


@pytest.mark.parametrize('source,case_id', [
    (f'<data><case xmlns="{CASE_XMLNS}" case_id="other"><close/></case></data>', 'target'),
    (f'<data><case xmlns="{CASE_XMLNS}" case_id="target"><close/></case>'
     f'<case xmlns="{CASE_XMLNS}" case_id="other"><close/></case></data>', 'target'),
    (f'<data><case xmlns="{CASE_XMLNS}" case_id="target"><update/></case></data>', 'target'),
])
def test_ambiguous_or_unrelated_closure_is_rejected(source, case_id):
    with pytest.raises(ValueError):
        without_single_case_close(source.encode(), case_id)
