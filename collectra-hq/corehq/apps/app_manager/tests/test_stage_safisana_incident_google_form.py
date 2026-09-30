"""Google incident questions must retain the existing Safisana case/export contract."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError
from lxml import etree

from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import NS
from corehq.apps.app_manager.management.commands.stage_safisana_incident_google_form import (
    CASE_PROPERTIES, DATETIME_CALCULATION, FORM_ID, INCIDENT_XMLNS,
    LEGACY_DATETIME_CALCULATION, PREFIX, Command, merged_case_updates, question_path,
    specification, upgrade_source,
)
from corehq.apps.app_manager.models.form_actions import ConditionalCaseUpdate, UpdateCaseAction
from corehq.apps.dashboard.operational_alerts import alert_from_form


def original_source():
    path = (Path(__file__).resolve().parents[5]
            / 'deploy/local-testing/recovery/processing-plant/processing-plant-form-recovery.json')
    return next(item['xml'].encode('utf-8') for item in json.loads(path.read_text())['forms']
                if item['form_id'] == FORM_ID)


def test_all_source_questions_types_choices_required_and_other_responses():
    root = etree.fromstring(upgrade_source(original_source()))
    spec = specification()
    assert len(spec['questions']) == 15
    for question in spec['questions']:
        path = question_path(question)
        control = root.xpath('//h:body//*[@ref=$path]', namespaces=NS, path=path)[0]
        bind = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=path)[0]
        assert (bind.get('required') == 'true()') == question['required']
        if question.get('choices'):
            assert etree.QName(control).localname == 'select1'
            assert control.xpath('./x:item/x:value/text()', namespaces=NS) == [
                value for value, label in question['choices']]
        if question['type'] == 'dropdown':
            assert control.get('appearance') == 'minimal'
        elif question['type'] == 'paragraph':
            assert control.get('appearance') == 'multiline'
        elif question['type'] == 'date':
            assert bind.get('type') == 'xsd:date'
        elif question['type'] == 'file_upload':
            assert bind.get('type') == 'binary'
            assert control.get('mediatype') == 'image/*'
        if question.get('other'):
            other = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=path + '_other')[0]
            assert other.get('required') == 'true()'
            assert other.get('relevant') == f"{path} = 'other'"


def test_legacy_paths_types_first_aid_rule_and_namespace_survive():
    before = etree.fromstring(original_source())
    revised = upgrade_source(original_source())
    after = etree.fromstring(revised)
    assert before.xpath('//x:instance/*', namespaces=NS)[0].tag == after.xpath(
        '//x:instance/*', namespaces=NS)[0].tag
    for bind in before.xpath('//x:model/x:bind', namespaces=NS):
        updated = after.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=bind.get('nodeset'))[0]
        assert bind.get('type') == updated.get('type')
        assert bind.get('relevant') == updated.get('relevant')
    incident_bind = after.xpath('//x:bind[@nodeset="/data/description/type_incident"]', namespaces=NS)[0]
    assert incident_bind.get('calculate') == (
        f"if({PREFIX}was_injured = 'yes', 'injury', {PREFIX}incident_kind)")
    assert upgrade_source(revised) == revised


def test_existing_custom_calculation_survives_and_conflicting_legacy_calculation_is_rejected():
    root = etree.fromstring(original_source())
    name_bind = root.xpath('//x:bind[@nodeset="/data/time_type/name"]', namespaces=NS)[0]
    name_bind.set('calculate', "'existing title calculation'")
    revised = etree.fromstring(upgrade_source(etree.tostring(root)))
    assert revised.xpath('//x:bind[@nodeset="/data/time_type/name"]/@calculate', namespaces=NS) == [
        "'existing title calculation'"]
    root.xpath('//x:bind[@nodeset="/data/description/type_incident"]', namespaces=NS)[0].set(
        'calculate', "'do not replace'")
    with pytest.raises(ValueError, match='cannot be replaced'):
        upgrade_source(etree.tostring(root))


def test_new_incident_submission_enters_dashboard_without_flagging_legacy_submissions():
    form = SimpleNamespace(xmlns=INCIDENT_XMLNS, form_id='incident',
                           received_on=datetime.now(UTC), form_data={
                               'needs_attention': 'yes', 'attention_note': 'A near miss at the loading area.'})
    alert = alert_from_form(form)
    assert alert['form_name'] == 'Incident report (SIO/EIO)'
    assert alert['severity'] == 'follow_up'
    assert 'near miss' in alert['note']
    form.form_data = {'description': {'description': 'Legacy report'}}
    assert alert_from_form(form) is None


def test_dry_run_keeps_case_actions_and_conflicting_property_stops_apply():
    app = Mock()
    form = Mock()
    form.actions.open_case.condition.type = 'always'
    form.actions.open_case.name_update.question_path = '/data/time_type/name'
    legacy = {'type_incident': ConditionalCaseUpdate(question_path='/data/description/type_incident')}
    form.actions.update_case = UpdateCaseAction(update=legacy)
    app.get_form.return_value = form
    app.fetch_attachment.return_value = original_source()
    module = 'corehq.apps.app_manager.management.commands.stage_safisana_incident_google_form'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(
            module + '.save_xform') as save:
        Command().handle(output_dir=directory, apply=False)
        save.assert_not_called()
        app.save.assert_not_called()
        assert form.actions.update_case.update == legacy
        form.actions.update_case.update['plant'] = ConditionalCaseUpdate(
            question_path='/data/custom_existing_plant')
        with pytest.raises(CommandError, match='mapping differs'):
            Command().handle(output_dir=directory, apply=True)
        save.assert_not_called()
        app.save.assert_not_called()


def test_case_updates_use_real_schema_and_preserve_existing_update_modes():
    legacy = ConditionalCaseUpdate(question_path='/data/description/type_incident', update_mode='edit')
    plant = ConditionalCaseUpdate(question_path=PREFIX + 'plant', update_mode='edit')
    action = UpdateCaseAction(update={'type_incident': legacy, 'plant': plant})
    action.update = merged_case_updates(action.update)
    assert all(isinstance(value, ConditionalCaseUpdate) for value in action.update.values())
    assert action.update['type_incident'].update_mode == 'edit'
    assert action.update['plant'].update_mode == 'edit'
    encoded = action.to_json()
    restored = UpdateCaseAction.wrap(encoded)
    for key in CASE_PROPERTIES:
        assert restored.update[key].question_path == PREFIX + key
    before = restored.to_json()
    restored.update = merged_case_updates(restored.update)
    assert restored.to_json() == before


def test_apply_saves_real_case_update_schema_and_can_be_rerun():
    app = Mock()
    form = Mock()
    form.actions.open_case.condition.type = 'always'
    form.actions.open_case.name_update.question_path = '/data/time_type/name'
    form.actions.update_case = UpdateCaseAction(update={
        'type_incident': ConditionalCaseUpdate(question_path='/data/description/type_incident'),
    })
    original = original_source()
    revised = upgrade_source(original)
    app.get_form.return_value = form
    app.fetch_attachment.side_effect = [original, revised, revised]
    module = 'corehq.apps.app_manager.management.commands.stage_safisana_incident_google_form'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(
            module + '.save_xform') as save:
        Command().handle(output_dir=directory, apply=True)
        save.assert_called_once_with(app, form, revised)
        app.save.assert_called_once()
        assert form.actions.update_case.update['plant'].question_path == PREFIX + 'plant'
        Command().handle(output_dir=directory, apply=True)
        assert save.call_count == 1
        assert app.save.call_count == 1


def test_timestamp_stays_blank_until_both_date_and_time_are_answered():
    root = etree.fromstring(upgrade_source(original_source()))
    expression = root.xpath('//x:bind[@nodeset="/data/time_type/date_time"]/@calculate', namespaces=NS)[0]
    assert expression == DATETIME_CALCULATION
    expression = expression.replace('if(', 'test:if(')
    extensions = {('urn:datetime-test', 'if'): lambda ctx, condition, yes, no: yes if condition else no}
    for date, time, expected in (
            ('', '', ''), ('2026-09-30', '', ''), ('', '10:30:00', ''),
            ('2026-09-30', '10:30:00', '2026-09-30T10:30:00')):
        instance = etree.fromstring(
            f'<data><google_incident><incident_date>{date}</incident_date>'
            f'<incident_time>{time}</incident_time></google_incident></data>')
        assert instance.xpath(expression, namespaces={'test': 'urn:datetime-test'},
                              extensions=extensions) == expected


def test_already_staged_draft_timestamp_is_repaired_without_changing_other_fields():
    correct = upgrade_source(original_source())
    broken = etree.fromstring(correct)
    broken.xpath('//x:bind[@nodeset="/data/time_type/date_time"]', namespaces=NS)[0].set(
        'calculate', LEGACY_DATETIME_CALCULATION)
    repaired = upgrade_source(etree.tostring(broken))
    assert etree.tostring(etree.fromstring(repaired)) == etree.tostring(etree.fromstring(correct))
    assert upgrade_source(repaired) == repaired


def test_visible_questions_have_valid_editor_group_parents():
    root = etree.fromstring(upgrade_source(original_source()))
    group = root.xpath('//h:body/x:group[@ref="/data/google_incident"]', namespaces=NS)[0]
    for question in specification()['questions']:
        path = question_path(question)
        control = root.xpath('//h:body//*[@ref=$path]', namespaces=NS, path=path)[0]
        assert control.getparent().get('ref') == path.rsplit('/', 1)[0]
    assert group.xpath('./x:group[@ref="/data/actions"]//x:select[@ref="/data/actions/first_aid_applied"]', namespaces=NS)
    # Simulate a previously staged flat layout, then repair it in place.
    body = group.getparent()
    for child in list(group):
        if child.get('ref'):
            body.append(child)
    body.remove(group)
    fixed = etree.fromstring(upgrade_source(etree.tostring(root)))
    assert fixed.xpath('//h:body/x:group[@ref="/data/google_incident"]', namespaces=NS)
