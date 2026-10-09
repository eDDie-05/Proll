import getpass
import os

from django.contrib.auth import password_validation
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User
from apps.accounts.services import sync_permissions_and_roles


class Command(BaseCommand):
    help = "Create a Super Administrator. Password is read from ADMIN_PASSWORD or prompted; never passed as an argument."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)

    def handle(self, *args, **opts):
        sync_permissions_and_roles()
        if User.objects.filter(username=opts["username"]).exists():
            raise CommandError("User already exists.")
        password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
        user = User(username=opts["username"], email=opts["email"], role=Role.objects.get(code="SUPER_ADMIN"),
                    is_staff=True, is_superuser=True)
        password_validation.validate_password(password, user)
        user.set_password(password)
        user.save()
        self.stdout.write(self.style.SUCCESS(f"Super Administrator '{user.username}' created."))
