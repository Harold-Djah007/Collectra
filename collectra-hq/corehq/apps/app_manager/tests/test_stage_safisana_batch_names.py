import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError
from lxml import etree

from corehq.apps.app_manager.management.commands.stage_safisana_batch_names import (
    BED, BED_CODES, DATE, FORM_ID, GENERATED_NAME, LEGACY_NAME, NAME_CALCULATION,
    NS, Command, upgrade_source,
)
from corehq.apps.app_manager.models.form_actions import ConditionalCaseUpdate, OpenCaseAction


def original_source():
    path = (Path(__file__).resolve().parents[5]
            / 'deploy/local-testing/recovery/processing-plant/processing-plant-form-recovery.json')
    return next(item['xml'].encode() for item in json.loads(path.read_text())['forms']
                if item['form_id'] == FORM_ID)


def test_today_is_hidden_bed_is_dropdown_and_name_is_readonly():
    root = etree.fromstring(upgrade_source(original_source()))
    assert not root.xpath('//h:body//*[@ref=$path]', namespaces=NS, path=DATE)
    assert not root.xpath('//h:body//*[@ref=$path]', namespaces=NS, path=LEGACY_NAME)
    assert root.xpath('//x:setvalue[@ref=$path]/@value', namespaces=NS, path=DATE) == ['today()']
    bed = root.xpath('//x:select1[@ref=$path]', namespaces=NS, path=BED)[0]
    assert bed.get('appearance') == 'minimal'
    assert bed.xpath('./x:item/x:value/text()', namespaces=NS) == list(BED_CODES)
    name = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=GENERATED_NAME)[0]
    assert name.get('type') == 'xsd:string'
    assert name.get('readonly') == 'true()'
    assert name.get('calculate') == NAME_CALCULATION


def test_generated_name_expression_has_exactly_eight_digits_and_no_suffix():
    root = etree.fromstring(upgrade_source(original_source()))
    expression = root.xpath('//x:bind[@nodeset=$path]/@calculate', namespaces=NS, path=GENERATED_NAME)[0]
    # Execute the actual XPath with JavaRosa-specific if/format-date functions
    # supplied through lxml; six-digit date + two-digit bed are tested together.
    expression = expression.replace('if(', 'jr:if(').replace('format-date(', 'jr:format-date(')
    def first(value):
        return value[0].text if isinstance(value, list) else value
    extensions = {
        ('urn:batch-test', 'if'): lambda ctx, condition, yes, no: yes if condition else no,
        ('urn:batch-test', 'format-date'): lambda ctx, date, fmt: first(date)[2:4] + first(date)[5:7] + first(date)[8:10],
    }
    for date in ('2026-09-30', '2005-01-02', '2030-12-31'):
        for bed, code in BED_CODES.items():
            data = etree.fromstring(f'<data><list><registration_date>{date}</registration_date><drying_bed_nmbr>{bed}</drying_bed_nmbr></list></data>')
            name = data.xpath(expression, namespaces={'jr': 'urn:batch-test'}, extensions=extensions)
            assert name == date[2:4] + date[5:7] + date[8:10] + code
            assert len(name) == 8 and name.isdigit()
    assert 'batch_on_bed_today' not in expression


def test_existing_numeric_fields_and_measurement_formulas_survive_and_rerun_is_unchanged():
    before = etree.fromstring(original_source())
    revised = upgrade_source(original_source())
    after = etree.fromstring(revised)
    for bind in before.xpath('//x:bind', namespaces=NS):
        updated = after.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=bind.get('nodeset'))[0]
        assert updated.get('type') == bind.get('type')
        if bind.get('calculate'):
            assert updated.get('calculate') == bind.get('calculate')
    assert before.xpath('//x:instance/*', namespaces=NS)[0].tag == after.xpath('//x:instance/*', namespaces=NS)[0].tag
    assert upgrade_source(revised) == revised
    before.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=LEGACY_NAME)[0].set('calculate', "'custom'")
    with pytest.raises(ValueError, match='calculation changed'):
        upgrade_source(etree.tostring(before))


def test_preview_and_apply_use_real_name_mapping_and_do_not_rewrite_cases():
    app = Mock()
    form = Mock()
    form.actions.open_case = OpenCaseAction(name_update=ConditionalCaseUpdate(
        question_path=LEGACY_NAME, update_mode='edit'))
    form.actions.open_case.condition.type = 'always'
    app.get_form.return_value = form
    original = original_source()
    revised = upgrade_source(original)
    app.fetch_attachment.side_effect = [original, original, revised, revised]
    module = 'corehq.apps.app_manager.management.commands.stage_safisana_batch_names'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(module + '.save_xform') as save:
        Command().handle(output_dir=directory, apply=False)
        app.save.assert_not_called()
        assert form.actions.open_case.name_update.question_path == LEGACY_NAME
        Command().handle(output_dir=directory, apply=True)
        app.save.assert_called_once()
        assert form.actions.open_case.name_update.question_path == GENERATED_NAME
        assert form.actions.open_case.name_update.update_mode == 'edit'
        Command().handle(output_dir=directory, apply=True)
        assert app.save.call_count == 1 and save.call_count == 1


def test_conflicting_case_mapping_prevents_any_save():
    app = Mock()
    app.get_form.return_value.actions.open_case.condition.type = 'always'
    app.get_form.return_value.actions.open_case.name_update.question_path = '/data/custom_name'
    module = 'corehq.apps.app_manager.management.commands.stage_safisana_batch_names'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(module + '.save_xform') as save:
        with pytest.raises(CommandError, match='mapping changed'):
            Command().handle(output_dir=directory, apply=True)
        save.assert_not_called()
        app.save.assert_not_called()


def test_automatic_date_has_no_unsupported_hidden_value_settings():
    root = etree.fromstring(upgrade_source(original_source()))
    bind = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=DATE)[0]
    assert bind.get('required') is None
    assert bind.get('constraint') is None
    assert not root.xpath('//h:body//*[@ref=$path]', namespaces=NS, path=DATE)
    assert root.xpath('//x:setvalue[@ref=$path]/@value', namespaces=NS, path=DATE) == ['today()']


def test_already_applied_draft_is_repaired_and_keeps_calculations():
    correct = upgrade_source(original_source())
    root = etree.fromstring(correct)
    bind = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=DATE)[0]
    bind.set('required', 'true()')
    bind.set('constraint', ". <= today() and . >= date('2000-01-01') and . <= date('2099-12-31')")
    bind.set('{http://commcarehq.org/xforms/vellum}constraint', '. <= today()')
    repaired = upgrade_source(etree.tostring(root))
    assert etree.tostring(etree.fromstring(repaired)) == etree.tostring(etree.fromstring(correct))
    assert upgrade_source(repaired) == repaired
