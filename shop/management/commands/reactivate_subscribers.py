from django.core.management.base import BaseCommand
from django.utils import timezone

from shop.models import EmailSubscription


class Command(BaseCommand):
    help = "Reactivate all inactive email subscribers"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many would be reactivated without making changes",
        )

    def handle(self, *args, **options):
        inactive = EmailSubscription.objects.filter(is_active=False)
        count = inactive.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("All email subscribers are already active."))
            return

        if options["dry_run"]:
            self.stdout.write(f"Would reactivate {count} inactive email subscribers.")
            return

        inactive.update(is_active=True, unsubscribed_at=None)
        self.stdout.write(
            self.style.SUCCESS(f"Successfully reactivated {count} email subscribers.")
        )
