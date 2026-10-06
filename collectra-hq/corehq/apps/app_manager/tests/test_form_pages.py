from lxml import etree
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from corehq.apps.app_manager.form_pages import NS, upgrade_form_pages


def form(body, binds='', data='<kind/><a/><b/><c/><d/>'):
    return (f'<h:html xmlns:h="{NS["h"]}" xmlns="{NS["x"]}" '
            'xmlns:xsd="http://www.w3.org/2001/XMLSchema">'
            f'<h:head><model><instance><data xmlns="urn:test">{data}</data></instance>'
            f'{binds}</model></h:head><h:body>{body}</h:body></h:html>').encode()


def choice():
    return ('<select1 ref="/data/kind"><label>Kind</label>'
            '<item><label>Other</label><value>different</value></item></select1>')


def test_other_uses_actual_choice_value_and_keeps_data_paths():
    source = form(choice() + '<input ref="/data/a"/>')
    revised, report = upgrade_form_pages(source)
    root = etree.fromstring(revised)
    bind = root.xpath('//x:bind[@nodeset="/data/kind_other"]', namespaces=NS)[0]
    assert bind.get('relevant') == "selected(/data/kind, 'different')"
    assert bind.get('required') == 'true()'
    assert root.xpath('//x:instance/*/*[local-name()="kind"]', namespaces=NS)
    page = root.xpath('//x:group[@appearance="field-list"]', namespaces=NS)[0]
    assert [n.get('ref') for n in page] == ['/data/kind', '/data/kind_other', '/data/a']
    assert report['other_fields_added'] == ['/data/kind_other']
    assert upgrade_form_pages(revised)[0] == revised


def test_existing_other_is_not_duplicated():
    source = form(choice() + '<input ref="/data/kind_other"/>',
                  '<bind nodeset="/data/kind_other" type="xsd:string" '
                  'relevant="/data/kind = \'different\'"/>', '<kind/><kind_other/>')
    revised, report = upgrade_form_pages(source)
    assert report['other_fields_added'] == []
    assert len(etree.fromstring(revised).xpath('//x:input', namespaces=NS)) == 1


def test_large_existing_page_is_split_without_changing_repeat_paths():
    controls = ''.join(f'<input ref="/data/{name}"/>' for name in ('kind', 'a', 'b', 'c', 'd'))
    source = form('<group ref="/data" appearance="field-list">' + controls + '</group>')
    revised, _ = upgrade_form_pages(source)
    root = etree.fromstring(revised)
    assert [n.get('ref') for n in root.xpath('//x:input', namespaces=NS)] == [
        '/data/kind', '/data/a', '/data/b', '/data/c', '/data/d']
    assert max(len(n) for n in root.xpath('//x:group[@appearance="field-list"]', namespaces=NS)) <= 4
    assert upgrade_form_pages(revised)[0] == revised


def test_existing_relevance_is_preserved_for_other():
    source = form(choice(), '<bind nodeset="/data/kind" relevant="/data/a = \'yes\'"/>')
    root = etree.fromstring(upgrade_form_pages(source)[0])
    assert root.xpath('//x:bind[@nodeset="/data/kind_other"]/@relevant', namespaces=NS) == [
        "(/data/a = 'yes') and (selected(/data/kind, 'different'))"]


def test_existing_relative_other_is_preserved():
    source = form(choice() + '<input ref="/data/kind_other"/>',
                  '<bind nodeset="/data/kind_other" type="xsd:string" '
                  'relevant="selected(../kind, \'different\')"/>', '<kind/><kind_other/>')
    revised, report = upgrade_form_pages(source)
    assert report['other_fields_added'] == []
    assert upgrade_form_pages(revised)[0] == revised


def test_dependencies_do_not_create_oversized_pages():
    controls = ''.join(f'<input ref="/data/{name}"/>' for name in ('kind', 'a', 'b', 'c', 'd'))
    binds = ''.join(f'<bind nodeset="/data/{name}" relevant="/data/{previous} != \'\'"/>'
                    for name, previous in zip(('a', 'b', 'c', 'd'), ('kind', 'a', 'b', 'c')))
    root = etree.fromstring(upgrade_form_pages(form(controls, binds))[0])
    assert [len(page) for page in root.xpath('//x:group[@appearance="field-list"]', namespaces=NS)] == [3, 2]


def test_nested_page_is_split():
    controls = ''.join(f'<input ref="/data/{name}"/>' for name in ('kind', 'a', 'b', 'c', 'd'))
    source = form('<group appearance="field-list"><group ref="/data">' + controls + '</group></group>')
    root = etree.fromstring(upgrade_form_pages(source)[0])
    assert [len(page) for page in root.xpath('//x:group[@appearance="field-list"]', namespaces=NS)] == [3, 2]


def test_other_stays_on_same_page_as_choice_at_boundary():
    source = form('<input ref="/data/a"/><input ref="/data/b"/><input ref="/data/c"/>' + choice())
    root = etree.fromstring(upgrade_form_pages(source)[0])
    select = root.xpath('//x:select1', namespaces=NS)[0]
    other = root.xpath('//x:input[@ref="/data/kind_other"]', namespaces=NS)[0]
    assert select.getparent() is other.getparent()


def test_failed_preflight_never_saves_application(tmp_path):
    from corehq.apps.app_manager.management.commands.update_form_pages import Command

    target = SimpleNamespace(unique_id='form-id', form_type='module_form', name={'en': 'Test'})
    app = Mock()
    app.name, app._id = 'Test', 'app-id'
    app.get_modules.return_value = [SimpleNamespace(get_forms=lambda: [target])]
    app.fetch_attachment.return_value = form(choice())
    module = 'corehq.apps.app_manager.management.commands.update_form_pages'
    with patch(module + '.get_apps_in_domain', return_value=[app]), \
            patch(module + '.validate_xform', side_effect=ValueError('Invalid form')):
        with pytest.raises(ValueError, match='Invalid form'):
            Command().handle('safisana', str(tmp_path), apply=True)
    app.save.assert_not_called()
    assert not (tmp_path / 'app-id').exists()


def test_preview_never_saves_or_requires_form_engine(tmp_path):
    from corehq.apps.app_manager.management.commands.update_form_pages import Command

    target = SimpleNamespace(unique_id='form-id', form_type='module_form', name={'en': 'Test'})
    app = Mock()
    app.name, app._id = 'Test', 'app-id'
    app.get_modules.return_value = [SimpleNamespace(get_forms=lambda: [target])]
    app.fetch_attachment.return_value = form(choice())
    module = 'corehq.apps.app_manager.management.commands.update_form_pages'
    with patch(module + '.get_apps_in_domain', return_value=[app]), \
            patch(module + '.validate_xform') as validate:
        Command().handle('safisana', str(tmp_path), apply=False)
    app.save.assert_not_called()
    validate.assert_not_called()
    assert (tmp_path / 'report.json').exists()
