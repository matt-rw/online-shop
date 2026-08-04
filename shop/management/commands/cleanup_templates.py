"""
Clean up email templates — remove seed/filler templates and reorganize folders.
Keeps: auto-triggered, targeted, and hand-crafted content templates.
Reorganizes into clear purpose-based folders.

Usage:
    python manage.py cleanup_templates --dry-run    # Preview
    python manage.py cleanup_templates              # Apply
"""

from django.core.management.base import BaseCommand

from shop.models.email import EmailTemplate


# Templates to keep by name (hand-crafted content)
KEEP_NAMES = {
    # Content templates
    "How Foundation Got Made", "Chicago × Seoul", "Why We Use Premium Blanks",
    "Two Friends One Brand", "What Discovery Means", "Foundation Breakdown",
    "How to Style Foundation", "Sizing and Fit Guide", "Checking In",
    "Why We Started This", "Summer Plans", "We Read Every Reply",
    "New Drop This Week", "Restock Alert", "Free Shipping Reminder",
    # Transactional
    "Welcome — Auto", "Order Confirmed", "Shipped", "Admin Order Alert", "Blank Canvas",
    # Targeted
    "Create Your Account", "Early Access", "Save Your Info",
    "Your Order History", "Be First",
    "How was it?", "Share your thoughts", "Quick review?",
    "Wear test complete", "Rate your purchase",
}

# New folder assignments
FOLDER_MAP = {
    # Transactional (auto-triggered)
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
    # Campaigns — storytelling
    "How Foundation Got Made": "campaigns",
    "Chicago × Seoul": "campaigns",
    "Why We Use Premium Blanks": "campaigns",
    "Two Friends One Brand": "campaigns",
    "What Discovery Means": "campaigns",
    "Why We Started This": "campaigns",
    # Campaigns — product/promo
    "Foundation Breakdown": "campaigns",
    "How to Style Foundation": "campaigns",
    "Sizing and Fit Guide": "campaigns",
    "New Drop This Week": "campaigns",
    "Restock Alert": "campaigns",
    "Free Shipping Reminder": "campaigns",
    # Campaigns — casual
    "Checking In": "campaigns",
    "Summer Plans": "campaigns",
    "We Read Every Reply": "campaigns",
}


class Command(BaseCommand):
    help = "Clean up email templates — remove filler, reorganize folders"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        all_templates = EmailTemplate.objects.all()
        total = all_templates.count()

        # Identify keepers
        keepers = all_templates.filter(name__in=KEEP_NAMES) | all_templates.filter(
            auto_trigger__in=["on_subscribe", "on_order", "on_shipping", "on_order_admin"]
        ) | all_templates.filter(
            target_audience__in=["no_account", "review_request"]
        )
        keeper_ids = set(keepers.values_list("id", flat=True))

        # Templates to delete
        to_delete = all_templates.exclude(id__in=keeper_ids)
        delete_count = to_delete.count()

        self.stdout.write(f"\nTotal templates: {total}")
        self.stdout.write(f"Keeping: {len(keeper_ids)}")
        self.stdout.write(f"Deleting: {delete_count}")

        if delete_count > 0:
            self.stdout.write(f"\nDeleting {delete_count} seed/filler templates...")
            if not dry_run:
                to_delete.delete()

        # Reorganize folders
        self.stdout.write(f"\nReorganizing folders...")
        for name, new_folder in FOLDER_MAP.items():
            t = EmailTemplate.objects.filter(name=name).first()
            if t and t.folder != new_folder:
                self.stdout.write(f"  {name}: {t.folder} → {new_folder}")
                if not dry_run:
                    t.folder = new_folder
                    t.save(update_fields=["folder"])

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run — no changes made."))
        else:
            remaining = EmailTemplate.objects.count()
            self.stdout.write(self.style.SUCCESS(f"\nDone. {remaining} templates remaining."))

            # Show final organization
            from django.db.models import Count
            folders = EmailTemplate.objects.values("folder").annotate(count=Count("id")).order_by("folder")
            self.stdout.write("\nFinal organization:")
            for f in folders:
                self.stdout.write(f"  {f['folder']}: {f['count']}")
