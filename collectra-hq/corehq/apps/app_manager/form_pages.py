"""Add presentation-only pages and conditional Other answers without moving data paths."""

import re

from lxml import etree

X = 'http://www.w3.org/2002/xforms'
NS = {'x': X, 'h': 'http://www.w3.org/1999/xhtml'}
CONTROLS = {'input', 'select', 'select1', 'upload', 'trigger', 'secret', 'range'}


def upgrade_form_pages(source, page_size=4):
    if page_size not in (3, 4):
        raise ValueError('Page size must be three or four')
    root = etree.fromstring(source, etree.XMLParser(resolve_entities=False, no_network=True))
    model = root.find('.//x:model', NS)
    body = root.find('h:body', NS)
    if model is None or body is None:
        raise ValueError('Missing form model or body')
    instance = model.find('x:instance', NS)
    data = instance[0]
    bindings = {b.get('nodeset'): b for b in model.findall('x:bind', NS)}
    added = []
    warnings = []
    changed = False
    for control in list(body.xpath('.//x:select | .//x:select1', namespaces=NS)):
        path = control.get('ref')
        if not path or not path.startswith('/' + etree.QName(data).localname + '/'):
            warnings.append('Choice control without a supported absolute data path')
            continue
        others = []
        for item in control.findall('x:item', NS):
            value = item.findtext('x:value', namespaces=NS)
            label = item.find('x:label', NS)
            labels = [''.join(label.itertext())] if label is not None else []
            if label is not None and label.get('ref'):
                match = re.fullmatch(r"jr:itext\(['\"]([^'\"]+)['\"]\)", label.get('ref'))
                if match:
                    labels.extend(root.xpath('//x:itext/x:translation/x:text[@id=$id]/x:value/text()',
                                             namespaces=NS, id=match[1]))
            if value and (value.lower() in ('other', 'others')
                          or any(re.match(r'^others?\b', text.strip(), re.I) for text in labels)):
                others.append(value)
        if not others:
            continue
        predicates = [f"selected({path}, '{value}')" for value in others if "'" not in value]
        if len(predicates) != len(others):
            warnings.append(f'Other value requires manual XPath quoting: {path}')
            continue
        existing = [b for b in bindings.values() if b.get('type') in ('xsd:string', 'string')
                    and b.get('relevant') and (path in b.get('relevant')
                         or (b.get('nodeset') == path + '_other'
                             and path.rsplit('/', 1)[1] in b.get('relevant')))
                    and any(f"'{value}'" in b.get('relevant') for value in others)
                    and body.xpath('.//x:input[@ref=$path]', namespaces=NS, path=b.get('nodeset'))]
        if existing:
            continue
        parent = data
        for segment in path.split('/')[2:-1]:
            matches = [node for node in parent if etree.QName(node).localname == segment]
            if len(matches) != 1:
                raise ValueError(f'Ambiguous instance path: {path}')
            parent = matches[0]
        name = path.rsplit('/', 1)[1] + '_other'
        if any(etree.QName(node).localname == name for node in parent):
            raise ValueError(f'Existing Other answer needs manual review: {path}')
        etree.SubElement(parent, etree.QName(parent).namespace and
                         f'{{{etree.QName(parent).namespace}}}{name}' or name)
        other_path = path.rsplit('/', 1)[0] + '/' + name
        relevant = ' or '.join(predicates)
        original = bindings.get(path)
        if original is not None and original.get('relevant'):
            relevant = f"({original.get('relevant')}) and ({relevant})"
        bind = etree.SubElement(model, f'{{{X}}}bind', nodeset=other_path,
                                type='xsd:string', relevant=relevant, required='true()')
        bindings[other_path] = bind
        detail = etree.Element(f'{{{X}}}input', ref=other_path)
        etree.SubElement(detail, f'{{{X}}}label').text = 'Other — please specify'
        control.addnext(detail)
        added.append(other_path)
        changed = True

    page_count = 0

    def arrange(parent):
        nonlocal changed, page_count
        if parent.get('appearance') == 'field-list':
            direct = [n for n in parent if isinstance(n.tag, str)
                      and etree.QName(n).localname in CONTROLS]
            nested = [n for n in parent if isinstance(n.tag, str)
                      and etree.QName(n).localname in ('group', 'repeat')]
            if len(direct) <= page_size and not nested:
                return
            del parent.attrib['appearance']
            changed = True
        for child in list(parent):
            if isinstance(child.tag, str) and etree.QName(child).localname in ('group', 'repeat'):
                arrange(child)
        run = []

        def flush():
            nonlocal changed, page_count
            if len(run) < 2:
                run.clear()
                return
            chunks = []
            chunk = []
            units = []
            for node in run:
                bind = bindings.get(node.get('ref'))
                previous = units[-1][-1].get('ref') if units else None
                if previous and bind is not None and previous in bind.get('relevant', '') and (
                        etree.QName(units[-1][-1]).localname in ('select', 'select1')
                        and etree.QName(node).localname == 'input'):
                    units[-1].append(node)
                else:
                    units.append([node])
            for unit in units:
                if chunk and len(chunk) + len(unit) > page_size:
                    chunks.append(chunk)
                    chunk = []
                chunk.extend(unit)
            if chunk:
                chunks.append(chunk)
            if len(chunks) > 1 and len(chunks[-1]) == 1 and len(chunks[-2]) >= 3:
                final = chunks[-2][-1]
                bind = bindings.get(final.get('ref'))
                preceding = chunks[-2][-2].get('ref')
                paired = (bind is not None and preceding
                          and preceding in bind.get('relevant', '')
                          and etree.QName(chunks[-2][-2]).localname in ('select', 'select1'))
                if not paired:
                    chunks[-1].insert(0, chunks[-2].pop())
            for chunk in chunks:
                page = etree.Element(f'{{{X}}}group', appearance='field-list')
                parent.insert(parent.index(chunk[0]), page)
                for node in chunk:
                    page.append(node)
                page_count += 1
            changed = True
            run.clear()

        for child in list(parent):
            if isinstance(child.tag, str) and etree.QName(child).localname in CONTROLS:
                run.append(child)
            else:
                flush()
        flush()

    arrange(body)
    return (etree.tostring(root, encoding='utf-8', xml_declaration=True) if changed else source,
            {'pages_added': page_count, 'other_fields_added': added, 'warnings': warnings})
