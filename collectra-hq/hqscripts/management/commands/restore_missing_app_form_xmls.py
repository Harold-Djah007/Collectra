import json
from pathlib import Path

from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app


class Command(BaseCommand):
    help = (
        "Restore missing application form XML attachments from a recovery JSON file. "
        "Readable form attachments are left untouched."
    )

    def add_arguments(self, parser):
        parser.add_argument("recovery_json")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be restored without writing anything.",
        )

    def handle(self, recovery_json, dry_run=False, **options):
        path = Path(recovery_json)
        if not path.is_file():
            raise CommandError(f"Recovery JSON not found: {path}")

        payload = json.loads(path.read_text(encoding="utf-8"))
        domain = payload.get("domain")
        app_id = payload.get("app_id")
        forms = payload.get("forms") or []

        if not domain or not app_id:
            raise CommandError("Recovery JSON must include domain and app_id")

        app = get_app(domain, app_id)
        if app is None:
            raise CommandError(f"Application not found: {domain}/{app_id}")

        current_forms = {
            form.unique_id: form
            for module in app.get_modules()
            for form in module.get_forms()
        }

        checked = 0
        readable = 0
        missing = []
        restored = []
        unavailable = []

        recovery_by_id = {
            item.get("form_id"): item for item in forms if item.get("form_id")
        }
        # Audit every form in the current app, including forms added after
        # the recovery export was made.
        for form_id, form in current_forms.items():
            xml = recovery_by_id.get(form_id, {}).get("xml")
            checked += 1
            filename = f"{form_id}.xml"

            try:
                # Bypass LazyBlobDoc's cached ResourceNotFound (and cached content).
                # A stale negative could otherwise replace a newly restored blob
                # with older XML from the recovery export on --apply.
                app.fetch_attachment(filename)
            except ResourceNotFound:
                missing.append((form_id, form.default_name()))
            else:
                readable += 1
                continue

            if not xml:
                unavailable.append((form_id, form.default_name()))
                continue

            xml_bytes = xml.encode("utf-8")
            try:
                etree.fromstring(xml_bytes)
            except Exception as exc:
                raise CommandError(
                    f"Recovery XML for {form.default_name()} ({form_id}) is not well-formed: {exc}"
                ) from exc

            if not dry_run:
                app.lazy_put_attachment(
                    xml_bytes,
                    filename,
                    content_type="application/xml",
                    content_length=len(xml_bytes),
                )
                restored.append((form_id, form.default_name(), len(xml_bytes)))

        self.stdout.write(f"APP: {app.name}")
        self.stdout.write(f"APP ID: {app_id}")
        self.stdout.write(f"FORMS CHECKED: {checked}")
        self.stdout.write(f"ALREADY READABLE: {readable}")
        self.stdout.write(f"MISSING XML ATTACHMENTS: {len(missing)}")

        for form_id, name in missing:
            self.stdout.write(f"MISSING: {form_id} | {name}")

        if unavailable:
            self.stdout.write(f"NO RECOVERY XML AVAILABLE: {len(unavailable)}")
            for form_id, name in unavailable:
                self.stdout.write(f"UNAVAILABLE: {form_id} | {name}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no changes written"))
            return

        if restored:
            app.save(increment_version=False)

        # Verify every restored attachment from a freshly loaded app.
        verify_app = get_app(domain, app_id)
        for form_id, name, expected_len in restored:
            filename = f"{form_id}.xml"
            data = verify_app.fetch_attachment(filename)
            if isinstance(data, str):
                data = data.encode("utf-8")
            if len(data) != expected_len:
                raise CommandError(
                    f"Verification length mismatch for {name} ({form_id}): "
                    f"expected {expected_len}, got {len(data)}"
                )

        self.stdout.write(f"RESTORED: {len(restored)}")
        for form_id, name, size in restored:
            self.stdout.write(f"RESTORED FORM: {form_id} | {name} | {size} bytes")

        if unavailable:
            raise CommandError(
                "Some missing forms did not have recovery XML in the supplied file."
            )

        self.stdout.write(self.style.SUCCESS("ALL AVAILABLE MISSING FORM XML ATTACHMENTS RESTORED AND VERIFIED"))
