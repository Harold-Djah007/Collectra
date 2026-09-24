"""Inspect existing case names before changing a live form's naming rule.

The report is written only to the requested local path. It never changes cases.
Case names may contain personal information; do not commit the report.
"""

import json
from collections import Counter
from pathlib import Path

from django.core.management.base import BaseCommand

from corehq.form_processor.models import CommCareCase


def summarize_cases(cases, sample_size=30):
    names = Counter(str(case.name or '') for case in cases)
    total = sum(names.values())
    numeric_eight = {name: count for name, count in names.items()
                     if len(name) == 8 and name.isascii() and name.isdecimal()}
    collisions = {name: count for name, count in names.items() if name and count > 1}
    return {
        'total': total,
        'distinct_names': len(names),
        'eight_digit_cases': sum(numeric_eight.values()),
        'duplicate_names': dict(sorted(collisions.items(), key=lambda item: (-item[1], item[0]))),
        'name_examples': sorted(names.items(), key=lambda item: (-item[1], item[0]))[:sample_size],
    }


class Command(BaseCommand):
    help = 'Write a read-only, local audit of current case names and duplicate names.'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--case-type', required=True)
        parser.add_argument('--output', required=True)

    def handle(self, domain, case_type, output, **options):
        cases = CommCareCase.objects.iter_cases(
            CommCareCase.objects.get_case_ids_in_domain(domain, type=case_type)
        )
        report = {'domain': domain, 'case_type': case_type,
                  **summarize_cases(cases)}
        path = Path(output).expanduser()
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        self.stdout.write(f"Audited {report['total']} {case_type} cases to {path}")
