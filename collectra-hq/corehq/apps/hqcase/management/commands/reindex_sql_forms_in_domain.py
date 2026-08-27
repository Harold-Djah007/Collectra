from django.core.management import BaseCommand, CommandError

from dimagi.utils.chunked import chunked

from corehq.apps.es.client import manager
from corehq.form_processor.models import XFormInstance
from corehq.pillows.xform import SqlFormReindexerFactory


def reindex_sql_forms_in_domain(domain):
    reindexer = SqlFormReindexerFactory(domain=domain).build()
    reindex_accessor = reindexer.doc_provider.reindex_accessor
    indexed_count = 0

    for state, _ in XFormInstance.STATES:
        all_doc_ids = XFormInstance.objects.get_form_ids_in_domain_by_state(domain, state)
        for doc_ids in chunked(all_doc_ids, 100):
            print('Reindexing doc_ids: {}'.format(','.join(doc_ids)))
            documents = [
                reindex_accessor.doc_to_json(form)
                for form in XFormInstance.objects.get_forms(list(doc_ids))
            ]
            documents = [document for document in documents if document]
            if not reindexer.doc_processor.process_bulk_docs(documents, None):
                raise CommandError('Elasticsearch rejected a batch of form submissions')
            indexed_count += len(documents)

    manager.index_refresh(reindexer.adapter.index_name)
    print('Successfully indexed {} submissions'.format(indexed_count))


class Command(BaseCommand):
    help = 'Reindex form submissions for a domain'

    def add_arguments(self, parser):
        parser.add_argument('domain')

    def handle(self, domain, *args, **options):
        reindex_sql_forms_in_domain(domain)
