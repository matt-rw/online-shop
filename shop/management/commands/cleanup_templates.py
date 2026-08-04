"""
Reorganize email templates into clear purpose-based folders.
Keeps all templates, just moves them into better categories.

Usage:
    python manage.py cleanup_templates --dry-run    # Preview
    python manage.py cleanup_templates              # Apply
"""

from django.core.management.base import BaseCommand
from django.db.models import Count

from shop.models.email import EmailTemplate


# Old folder → new folder mapping for bulk reassignment
FOLDER_REMAP = {
    "storytelling": "brand-story",
    "casual": "casual",
    "direct": "product",
    "minimal": "minimal",
    "urgent": "promo",
    "transactional": "automatic",
}

# Specific templates that need precise folder placement
SPECIFIC_FOLDERS = {
    # Auto-triggered
    "Welcome — Auto": "automatic",
    "Order Confirmed": "automatic",
    "Shipped": "automatic",
    "Admin Order Alert": "automatic",
    # Targeted
    "Create Your Account": "targeted",
    "Early Access": "targeted",
    "Save Your Info": "targeted",
    "Your Order History": "targeted",
    "Be First": "targeted",
    "How was it?": "targeted",
    "Share your thoughts": "targeted",
    "Quick review?": "targeted",
    "Wear test complete": "targeted",
    "Rate your purchase": "targeted",
}


class Command(BaseCommand):
    help = "Reorganize email templates into purpose-based folders"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        total = EmailTemplate.objects.count()
        self.stdout.write(f"\nTotal templates: {total}")

        # Show current organization
        self.stdout.write("\nCurrent folders:")
        for f in EmailTemplate.objects.values("folder").annotate(count=Count("id")).order_by("folder"):
            self.stdout.write(f"  {f['folder']}: {f['count']}")

        moved = 0

        # 1. Move specific named templates first
        for name, new_folder in SPECIFIC_FOLDERS.items():
            t = EmailTemplate.objects.filter(name=name).first()
            if t and t.folder != new_folder:
                self.stdout.write(f"  {name}: {t.folder} → {new_folder}")
                if not dry_run:
                    t.folder = new_folder
                    t.save(update_fields=["folder"])
                moved += 1

        # 2. Bulk remap remaining templates by old folder name
        for old_folder, new_folder in FOLDER_REMAP.items():
            count = EmailTemplate.objects.filter(folder=old_folder).count()
            if count > 0:
                self.stdout.write(f"  {old_folder} ({count}) → {new_folder}")
                if not dry_run:
                    EmailTemplate.objects.filter(folder=old_folder).update(folder=new_folder)
                moved += count

        if dry_run:
            self.stdout.write(self.style.WARNING(f"\nDry run — {moved} templates would be moved."))
        else:
            self.stdout.write(self.style.SUCCESS(f"\nDone. {moved} templates reorganized."))

        # Show final organization
        self.stdout.write("\nNew folders:")
        for f in EmailTemplate.objects.values("folder").annotate(count=Count("id")).order_by("folder"):
            self.stdout.write(f"  {f['folder']}: {f['count']}")
