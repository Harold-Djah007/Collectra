"""Restore selected derived state when Kafka no longer retains its history."""

import json


REBUILDABLE = {'UserPillow', 'group-pillow', 'KafkaDomainPillow',
               'FormSubmissionMetadataTrackerPillow', 'UnknownUsersPillow'}


def rebuild_from_source(names, root, report):
    """Rebuild current state before moving to the first retained Kafka event.

    Never change forms/cases, send messages, or purge an index. Existing derived
    documents and the metadata fields updated by this pass are backed up first.
    """
    from corehq.apps.users.models import WebUser, CommCareUser
    from corehq.util.doc_processor.couch import DocsIterator
    from corehq.apps.es.users import user_adapter

    root.mkdir(parents=True, exist_ok=False)
    counts = {}

    def index_source(label, classes, adapter):
        from couchdbkit.exceptions import ResourceNotFound
        source_types = {cls.__name__ for cls in classes}
        old_ids = set()
        with (root / f'{label}-index.jsonl').open('x') as backup:
            for hit in adapter.scroll({'query': {'match_all': {}}}):
                backup.write(json.dumps(hit, default=str) + '\n')
                doc = hit.get('_source', hit)
                if doc.get('doc_type', '').removesuffix('-Deleted') in source_types:
                    old_ids.add(hit.get('_id') or doc.get('doc_id'))
        count = 0
        current_ids = set()
        for cls in classes:
            chunk = []
            for doc in DocsIterator(cls):
                current_ids.add(doc['_id'])
                chunk.append(doc)
                if len(chunk) == 50:
                    adapter.bulk_index(chunk, refresh=True)
                    count += len(chunk)
                    chunk = []
            if chunk:
                adapter.bulk_index(chunk, refresh=True)
                count += len(chunk)
        counts[label] = count
        # Reconcile stale source-backed search entries, preserving unknown/demo
        # users. Confirm current deletion to avoid a concurrent-create race.
        stale = []
        for doc_id in old_ids - current_ids:
            try:
                doc = classes[0].get_db().get(doc_id)
            except ResourceNotFound:
                stale.append(doc_id)
            else:
                if doc.get('doc_type', '').endswith('-Deleted'):
                    stale.append(doc_id)
        if stale:
            adapter.bulk_delete(stale, refresh=True)
        counts[label + '_stale_removed'] = len(stale)
        report(f'AUTHORITATIVE {label}: {count} documents')

    form_rebuild = bool(names & {'FormSubmissionMetadataTrackerPillow', 'UnknownUsersPillow'})
    if names & {'UserPillow', 'group-pillow'} or form_rebuild:
        with (root / 'user-reporting-metadata.jsonl').open('x') as backup:
            for cls in (WebUser, CommCareUser):
                for doc in DocsIterator(cls):
                    previous = {'id': doc['_id'], 'reporting_metadata': doc.get('reporting_metadata')}
                    backup.write(json.dumps(previous, default=str) + '\n')
        index_source('users', (WebUser, CommCareUser), user_adapter)
    if 'group-pillow' in names:
        from corehq.apps.groups.models import Group
        from corehq.apps.es.groups import group_adapter
        index_source('groups', (Group,), group_adapter)
    if 'KafkaDomainPillow' in names:
        from corehq.apps.domain.models import Domain
        from corehq.apps.es.domains import domain_adapter
        index_source('domains', (Domain,), domain_adapter)
    if form_rebuild:
        from corehq.apps.app_manager.models import Application, RemoteApp, LinkedApplication
        from corehq.form_processor.backends.sql.dbaccessors import FormReindexAccessor
        from corehq.apps.change_feed.document_types import change_meta_from_doc
        from corehq.apps.change_feed.data_sources import FORM_SQL
        from pillowtop.feed.interface import Change
        from pillowtop.processors.form import FormSubmissionMetadataTrackerProcessor
        from corehq.pillows.user import UnknownUsersProcessor

        with (root / 'app-submission-flags.jsonl').open('x') as backup:
            for cls in (Application, RemoteApp, LinkedApplication):
                for doc in DocsIterator(cls):
                    previous = {'id': doc['_id'], 'has_submissions': doc.get('has_submissions')}
                    backup.write(json.dumps(previous) + '\n')
        processors = []
        if 'FormSubmissionMetadataTrackerPillow' in names:
            processors.append(FormSubmissionMetadataTrackerProcessor())
        if 'UnknownUsersPillow' in names:
            processors.append(UnknownUsersProcessor())
        access = FormReindexAccessor(include_attachments=False)
        count = 0
        for alias in access.sql_db_aliases:
            maximum = access.query(alias).order_by('-pk').values_list('pk', flat=True).first()
            last = None
            while maximum is not None:
                batch = list(access.query(alias, last).filter(pk__lte=maximum).order_by('pk')[:100])
                if not batch:
                    break
                for form in batch:
                    doc = access.doc_to_json(form)
                    if not doc:
                        raise RuntimeError('Authoritative form content is missing; rebuild stopped.')
                    metadata = change_meta_from_doc(doc, FORM_SQL, 'form_processor_xforminstancesql')
                    change = Change(doc['_id'], None, document=doc, metadata=metadata)
                    for processor in processors:
                        processor.process_change(change)
                    count += 1
                last = batch[-1].pk
                if count % 1000 == 0:
                    report(f'AUTHORITATIVE forms: {count} processed')
        counts['forms'] = count
        report(f'AUTHORITATIVE forms: {count} complete')
    (root / 'completed.json').write_text(json.dumps(counts, indent=2))
    return counts
