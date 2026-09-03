from django.core.management.base import BaseCommand, CommandError
from django.core.validators import ValidationError, validate_email

from corehq.apps.domain.models import Domain
from corehq.apps.users.models import Invitation, WebUser


class Command(BaseCommand):
    help = (
        "Ensure a web user is an Admin of a project space (and optionally a "
        "site superuser). Use this when switching from a test account "
        "(e.g. harold@example.com) to a real email that cannot see the project."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "username",
            help="Web user email, e.g. harold.djah@safisana.org",
        )
        parser.add_argument(
            "domain",
            help="Project space name, e.g. safisana",
        )
        parser.add_argument(
            "--make-superuser",
            action="store_true",
            help="Also grant Django/HQ superuser flags (recommended for the primary operator).",
        )
        parser.add_argument(
            "--accept-invite",
            action="store_true",
            help="If a pending invitation exists for this email+domain, mark it accepted.",
        )

    def handle(self, username, domain, **options):
        username = username.strip().lower()
        domain = domain.strip().lower()
        try:
            validate_email(username)
        except ValidationError as exc:
            raise CommandError("Username must be a valid email address") from exc

        domain_obj = Domain.get_by_name(domain)
        if not domain_obj:
            raise CommandError(f'Project space "{domain}" was not found.')

        user = WebUser.get_by_username(username)
        if not user:
            raise CommandError(
                f'No web user exists for "{username}". '
                "Have them accept an invite first, or create the account with "
                f"`uv run python manage.py make_superuser {username}`."
            )

        self.stdout.write(f"User: {user.username} (id={user.user_id})")
        self.stdout.write(f"Domains before: {user.domains}")

        if not user.is_member_of(domain):
            self.stdout.write(f'→ Adding "{username}" to "{domain}" as Admin...')
            user.add_as_web_user(domain, role="admin")
        else:
            self.stdout.write(f'✓ Already a member of "{domain}"')
            if not user.is_domain_admin(domain):
                self.stdout.write("→ Promoting to Admin role...")
                user.set_role(domain, "admin")
                user.save(domains_to_sync_usercase=[domain])
            else:
                self.stdout.write("✓ Already Admin on this project")

        # Reload after membership changes
        user = WebUser.get_by_username(username)
        self.stdout.write(f"Domains after: {user.domains}")
        self.stdout.write(
            f"is_domain_admin({domain})={user.is_domain_admin(domain)} "
            f"edit_web_users={user.has_permission(domain, 'edit_web_users')}"
        )

        if options["accept_invite"]:
            updated = Invitation.objects.filter(
                domain=domain, email=username, is_accepted=False
            ).update(is_accepted=True)
            if updated:
                self.stdout.write(f"→ Marked {updated} pending invitation(s) accepted")
            else:
                self.stdout.write("✓ No pending invitation to accept")

        if options["make_superuser"]:
            changed = False
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if not user.can_assign_superuser:
                user.can_assign_superuser = True
                changed = True
            if changed:
                user.save()
                self.stdout.write("→ Granted superuser/staff flags")
            else:
                self.stdout.write("✓ Already a superuser")

        self.stdout.write(self.style.SUCCESS(
            f'Done. Log out, then log in as {username} — "{domain}" should appear.'
        ))
        self.stdout.write(
            "Web Users page: "
            f"/a/{domain}/settings/users/web/"
        )
