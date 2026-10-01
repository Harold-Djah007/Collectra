from corehq.apps.app_manager.form_readiness import inspect_form_xml


def source(body='', binds=''):
    return f'''<h:html xmlns:h="http://www.w3.org/1999/xhtml"
        xmlns="http://www.w3.org/2002/xforms"><h:head><model>
        <instance><data xmlns="urn:test"><answer/></data></instance>{binds}
        </model></h:head><h:body>{body}</h:body></h:html>'''


def test_valid_form_with_dynamic_choices_and_calculation():
    xml = source('<select1 ref="/data/answer"><itemset nodeset="instance(\'beds\')/bed"/></select1>',
                 '<bind nodeset="/data/answer" type="xsd:string" calculate="concat(\'26\', \'01\')"/>')
    assert inspect_form_xml(xml) == []


def test_empty_and_malformed_xml():
    assert inspect_form_xml('') == ['Form XML is empty']
    assert inspect_form_xml('<broken>')[0].startswith('Invalid XML:')


def test_duplicate_bind_and_choices():
    xml = source('<select1 ref="/data/answer"><item><value>yes</value></item>'
                 '<item><value>yes</value></item><item><value/></item></select1>',
                 '<bind nodeset="/data/answer"/><bind nodeset="/data/answer"/>')
    problems = inspect_form_xml(xml)
    assert 'Duplicate bind: /data/answer' in problems
    assert "Duplicate choice value 'yes': /data/answer" in problems
    assert 'Empty choice value: /data/answer' in problems


def test_entity_declarations_are_rejected():
    assert inspect_form_xml('<!DOCTYPE html [<!ENTITY test "value">]>' + source()) == [
        'Form XML contains a DTD or entity declaration']


def test_missing_form_structure_is_reported():
    assert len(inspect_form_xml('<data/>')) == 3


def test_translation_ids_are_unique_per_language():
    translation = '<itext><translation lang="en"><text id="label"/><text id="label"/></translation></itext>'
    assert inspect_form_xml(source(binds=translation)) == ["Duplicate translation ID 'label' in en"]
    translated = '<itext><translation lang="en"><text id="label"/></translation>'
    translated += '<translation lang="fr"><text id="label"/></translation></itext>'
    assert inspect_form_xml(source(binds=translated)) == []
