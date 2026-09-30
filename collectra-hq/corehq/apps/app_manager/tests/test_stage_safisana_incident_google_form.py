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
    FORM_ID, INCIDENT_XMLNS, PREFIX, Command, question_path,
    specification, upgrade_source,
)
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
    legacy = {'type_incident': '/data/description/type_incident'}
    form.actions.update_case.update = dict(legacy)
    app.get_form.return_value = form
    app.fetch_attachment.return_value = original_source()
    module = 'corehq.apps.app_manager.management.commands.stage_safisana_incident_google_form'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(
            module + '.save_xform') as save:
        Command().handle(output_dir=directory, apply=False)
        save.assert_not_called()
        app.save.assert_not_called()
        assert form.actions.update_case.update == legacy
        form.actions.update_case.update['plant'] = '/data/custom_existing_plant'
        with pytest.raises(CommandError, match='mapping differs'):
            Command().handle(output_dir=directory, apply=True)
        save.assert_not_called()
        app.save.assert_not_called()
