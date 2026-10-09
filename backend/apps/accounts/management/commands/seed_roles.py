from django.core.management.base import BaseCommand

from apps.accounts.services import sync_permissions_and_roles


class Command(BaseCommand):
    help = "Create/refresh permission catalog and default system roles."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Reset system role permissions to defaults.")

    def handle(self, *args, **opts):
        perms = sync_permissions_and_roles(reset_role_permissions=opts["reset"])
        self.stdout.write(self.style.SUCCESS(f"Synced {len(perms)} permissions and default roles."))
