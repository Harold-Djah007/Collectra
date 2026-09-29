from django.core.management import BaseCommand, CommandError

from dimagi.utils.chunked import chunked

from corehq.apps.es.cases import CaseES, case_adapter
from corehq.apps.es.client import manager
from corehq.form_processor.backends.sql.dbaccessors import CaseReindexAccessor, iter_all_ids
from corehq.form_processor.models import CommCareCase


class Command(BaseCommand):
    help = (
        "Compare SQL cases for a domain with the Elasticsearch case index. "
        "Optionally repair missing or stale index records."
    )

    def add_arguments(self, parser):
        parser.add_argument("domain")
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Reindex missing or stale cases into Elasticsearch.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=200,
            help="Number of case IDs to inspect per Elasticsearch query (default: 200).",
        )

    def handle(self, domain, repair=False, batch_size=200, **options):
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1")

        accessor = CaseReindexAccessor(domain=domain)
        database_ids = list(iter_all_ids(accessor))

        missing = []
        stale = []
        checked = 0
        repaired = 0

        for case_ids in chunked(database_ids, batch_size):
            case_ids = list(case_ids)
            hits = CaseES().domain(domain).case_ids(case_ids).run().hits
            indexed = {
                (hit.get("_id") or hit.get("case_id")): hit
                for hit in hits
                if hit.get("_id") or hit.get("case_id")
            }

            for case_id in case_ids:
                checked += 1
                case = CommCareCase.objects.get_case(case_id, domain)
                hit = indexed.get(case_id)

                if hit is None:
                    missing.append(case_id)
                    if repair:
                        case_adapter.index(case)
                        repaired += 1
                    continue

                indexed_closed = hit.get("closed")
                if indexed_closed is not None and bool(indexed_closed) != bool(case.closed):
                    stale.append(case_id)
                    if repair:
                        case_adapter.index(case)
                        repaired += 1

        if repair and repaired:
            manager.index_refresh(case_adapter.index_name)

        self.stdout.write("DOMAIN: {}".format(domain))
        self.stdout.write("DATABASE CASES: {}".format(len(database_ids)))
        self.stdout.write("CHECKED: {}".format(checked))
        self.stdout.write("MISSING FROM CASE INDEX: {}".format(len(missing)))
        self.stdout.write("STALE OPEN/CLOSED STATUS: {}".format(len(stale)))
        if missing:
            self.stdout.write("MISSING IDS: {}".format(",".join(missing)))
        if stale:
            self.stdout.write("STALE IDS: {}".format(",".join(stale)))
        if repair:
            self.stdout.write("REPAIRED: {}".format(repaired))

        # A non-repair audit should fail loudly so scripts/CI can detect drift.
        if (missing or stale) and not repair:
            raise CommandError(
                "Case search index drift detected. Re-run with --repair to fix it."
            )

        self.stdout.write(self.style.SUCCESS("Case search index audit complete."))
