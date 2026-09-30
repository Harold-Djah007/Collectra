"""Operational recovery must preserve legacy exports and restore dashboard inputs."""

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.core.management.base import CommandError
from lxml import etree

from corehq.apps.app_manager.management.commands.preview_safisana_alert_forms import (
    FORM_IDS, MORNING_STATUS_LABELS, NS, STATUS_VALUES,
)
from corehq.apps.app_manager.management.commands.repair_safisana_operational_questions import (
    Command, FORM_NAMES, upgrade_source,
)
from corehq.apps.dashboard.operational_alerts import alert_from_form


def originals():
    path = (Path(__file__).resolve().parents[5]
            / 'deploy/local-testing/recovery/processing-plant/processing-plant-form-recovery.json')
    return {item['form_id']: item['xml'].encode('utf-8')
            for item in json.loads(path.read_text())['forms']}


def test_recovered_forms_preserve_calculations_paths_namespace_and_support_repeat_runs():
    sources = originals()
    for slug, form_id in FORM_IDS.items():
        before = etree.fromstring(sources[form_id])
        revised = upgrade_source(sources[form_id], FORM_NAMES[slug])
        after = etree.fromstring(revised)
        for bind in before.xpath('//x:model/x:bind[@calculate]', namespaces=NS):
            updated = after.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=bind.get('nodeset'))[0]
            assert updated.get('calculate') == bind.get('calculate')
        assert set(before.xpath('//x:bind/@nodeset', namespaces=NS)) <= set(
            after.xpath('//x:bind/@nodeset', namespaces=NS))
        assert before.xpath('//x:model/x:instance/*', namespaces=NS)[0].tag == after.xpath(
            '//x:model/x:instance/*', namespaces=NS)[0].tag
        assert upgrade_source(revised, FORM_NAMES[slug]) == revised


def test_morning_three_choices_and_conditional_notes_match_dashboard_fields():
    revised = upgrade_source(originals()[FORM_IDS['morning-checks']], 'Morning Checks Daily')
    root = etree.fromstring(revised)
    data = {}
    for path in MORNING_STATUS_LABELS:
        assert root.xpath('//x:select1[@ref=$path]/x:item/x:value/text()',
                          namespaces=NS, path=path) == list(STATUS_VALUES)
        note_path = path.removesuffix('_status') + '_issue_note'
        bind = root.xpath('//x:bind[@nodeset=$path]', namespaces=NS, path=note_path)[0]
        assert bind.get('relevant') == f"{path} = 'needs_attention'"
        group, field = path.split('/')[-2:]
        data.setdefault(group, {}).update({field: 'needs_attention',
                                          field.removesuffix('_status') + '_issue_note': 'Test issue'})
    form = SimpleNamespace(xmlns=etree.QName(root.xpath('//x:instance/*', namespaces=NS)[0]).namespace,
                           form_data=data, form_id='test', received_on=datetime.now(UTC))
    alert = alert_from_form(form)
    assert len(alert['checks']) == 12
    assert all('Test issue' in check for check in alert['checks'])


def test_partial_issue_note_version_requires_manual_review():
    revised = upgrade_source(originals()[FORM_IDS['morning-checks']], 'Morning Checks Daily')
    root = etree.fromstring(revised)
    bind = root.xpath('//x:bind[contains(@nodeset, "_issue_note")]', namespaces=NS)[0]
    bind.getparent().remove(bind)
    with pytest.raises(ValueError, match='only some issue-note fields'):
        upgrade_source(etree.tostring(root), 'Morning Checks Daily')


def test_invalid_second_form_stops_before_any_draft_is_saved():
    sources = originals()
    app = Mock()
    app.fetch_attachment.side_effect = [sources[FORM_IDS['morning-checks']], b'<invalid/>']
    module = 'corehq.apps.app_manager.management.commands.repair_safisana_operational_questions'
    with TemporaryDirectory() as directory, patch(module + '.get_app', return_value=app), patch(
            module + '.save_xform') as save:
        with pytest.raises(CommandError):
            Command().handle(output_dir=directory, apply=True)
        save.assert_not_called()
        app.save.assert_not_called()
