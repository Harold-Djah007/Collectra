from io import BytesIO

import pytest
from openpyxl import Workbook

from corehq.apps.app_manager.xlsform import XlsFormError, build_xform, parse_xlsform


def workbook(rows):
    book = Workbook()
    sheet = book.active
    sheet.title = 'survey'
    sheet.append(['type', 'name', 'label'])
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    book.save(stream)
    stream.seek(0)
    return stream


@pytest.mark.parametrize('metadata', ['start', 'today'])
@pytest.mark.parametrize('nested', [False, True])
def test_repeat_metadata_is_rejected_instead_of_silently_left_blank(metadata, nested):
    rows = [['begin repeat', 'visits', 'Visits']]
    if nested:
        rows.append(['begin group', 'details', 'Details'])
    rows.append([metadata, 'captured', ''])
    if nested:
        rows.append(['end group', '', ''])
    rows.append(['end repeat', '', ''])
    definition = parse_xlsform(workbook(rows))
    assert any('outside repeats' in error.message for error in definition.errors)
    with pytest.raises(XlsFormError):
        build_xform(definition)


@pytest.mark.parametrize('metadata', ['start', 'today'])
def test_metadata_in_non_repeated_group_is_supported(metadata):
    definition = parse_xlsform(workbook([
        ['begin group', 'details', 'Details'], [metadata, 'captured', ''],
        ['end group', '', ''], ['text', 'answer', 'Answer'],
    ]))
    assert not definition.errors
    assert 'xforms-ready' in build_xform(definition)
