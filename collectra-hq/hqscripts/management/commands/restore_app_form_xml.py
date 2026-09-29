from pathlib import Path

from couchdbkit import ResourceNotFound
from django.core.management.base import BaseCommand, CommandError
from lxml import etree

from corehq.apps.app_manager.dbaccessors import get_app


class Command(BaseCommand):
    help = "Restore one missing application form XML attachment from a local XML file."

    def add_arguments(self, parser):
        parser.add_argument("domain")
        parser.add_argument("app_id")
        parser.add_argument("form_id")
        parser.add_argument("xml_path")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Overwrite an attachment that is currently readable.",
        )

    def handle(self, domain, app_id, form_id, xml_path, force=False, **options):
        app = get_app(domain, app_id)
        if app is None:
            raise CommandError(f"Application not found: {domain}/{app_id}")

        matches = [
            form
            for module in app.get_modules()
            for form in module.get_forms()
            if form.unique_id == form_id
        ]
        if len(matches) != 1:
            raise CommandError(
                f"Expected exactly one form with unique_id {form_id!r}; found {len(matches)}"
            )

        form = matches[0]
        filename = f"{form_id}.xml"
        path = Path(xml_path)
        if not path.is_file():
            raise CommandError(f"XML file not found: {path}")

        xml_bytes = path.read_bytes()
        try:
            etree.fromstring(xml_bytes)
        except Exception as exc:
            raise CommandError(f"Recovery XML is not well-formed: {exc}") from exc

        try:
            # Inspect the actual blob; the lazy cache can retain a missing-file
            # result even after the original file has been restored.
            current = app.fetch_attachment(filename)
        except ResourceNotFound:
            current = None

        if current is not None and not force:
            raise CommandError(
                f"{filename} is already readable. Re-run with --force only if overwrite is intended."
            )

        self.stdout.write(f"APP: {app.name}")
        self.stdout.write(f"FORM: {form.default_name()}")
        self.stdout.write(f"ATTACHMENT: {filename}")
        self.stdout.write(f"RECOVERY BYTES: {len(xml_bytes)}")

        app.lazy_put_attachment(
            xml_bytes,
            filename,
            content_type="application/xml",
            content_length=len(xml_bytes),
        )
        app.save(increment_version=False)

        verify = get_app(domain, app_id).fetch_attachment(filename)
        if isinstance(verify, str):
            verify = verify.encode("utf-8")

        if verify != xml_bytes:
            raise CommandError("Attachment write completed but verification content did not match.")

        self.stdout.write(self.style.SUCCESS("FORM XML RESTORED AND VERIFIED"))
