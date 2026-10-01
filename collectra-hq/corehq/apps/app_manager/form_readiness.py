"""Read-only checks for form storage and common designer failures."""

from collections import Counter

from lxml import etree


NS = {'h': 'http://www.w3.org/1999/xhtml', 'x': 'http://www.w3.org/2002/xforms'}


def inspect_form_xml(source):
    problems = []
    if not source or not source.strip():
        return ['Form XML is empty']
    source = source.encode('utf-8') if isinstance(source, str) else source
    try:
        root = etree.fromstring(source, etree.XMLParser(resolve_entities=False, no_network=True))
    except (etree.XMLSyntaxError, ValueError) as error:
        return [f'Invalid XML: {error}']
    if root.getroottree().docinfo.doctype or any(root.iter(etree.Entity)):
        return ['Form XML contains a DTD or entity declaration']
    for expression, label in (
        ('/h:html/h:head/x:model', 'model'),
        ('/h:html/h:body', 'body'),
        ('/h:html/h:head/x:model/x:instance[1]/*', 'primary instance'),
    ):
        if len(root.xpath(expression, namespaces=NS)) != 1:
            problems.append(f'Expected exactly one {label}')
    binds = root.xpath('//x:model/x:bind/@nodeset', namespaces=NS)
    for path, count in Counter(binds).items():
        if count > 1:
            problems.append(f'Duplicate bind: {path}')
    for control in root.xpath('//h:body//x:select | //h:body//x:select1', namespaces=NS):
        values = control.xpath('./x:item/x:value/text()', namespaces=NS)
        for value, count in Counter(values).items():
            if count > 1:
                problems.append(f'Duplicate choice value {value!r}: {control.get("ref", "unknown question")}')
        if any(not (value.text or '').strip() for value in control.xpath('./x:item/x:value', namespaces=NS)):
            problems.append(f'Empty choice value: {control.get("ref", "unknown question")}')
    for translation in root.xpath('//x:itext/x:translation', namespaces=NS):
        for text_id, count in Counter(translation.xpath('./x:text/@id', namespaces=NS)).items():
            if count > 1:
                problems.append(f'Duplicate translation ID {text_id!r} in {translation.get("lang")}')
    return problems
