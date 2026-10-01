from corehq.apps.app_manager.management.commands.audit_safisana_upgrade import compare_contracts


def test_upgrade_audit_reports_existing_schema_and_formula_changes():
    old = {'form-id': {'xmlns': 'legacy', 'fields': {
        '/data/reading': {'type': 'xsd:int', 'calculate': '1 + 2', 'constraint': None},
        '/data/old': {'type': 'xsd:string', 'calculate': None, 'constraint': None},
    }}}
    new = {'form-id': {'xmlns': 'legacy', 'fields': {
        '/data/reading': {'type': 'xsd:int', 'calculate': '1 + 3', 'constraint': None},
    }}, 'new-form': {'xmlns': 'new', 'fields': {}}}
    report = compare_contracts(old, new)
    assert report['removed_form_ids'] == []
    assert report['added_form_ids'] == ['new-form']
    assert report['removed_field_paths'] == [{'form_id': 'form-id', 'path': '/data/old'}]
    assert report['changes_to_existing_fields'] == [
        {'form_id': 'form-id', 'path': '/data/reading', 'kind': 'calculate',
         'before': '1 + 2', 'after': '1 + 3'},
    ]
