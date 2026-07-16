"""Set category display order."""
from django.core.management.base import BaseCommand
from shop.models.product import Category


class Command(BaseCommand):
    help = "Set category display order: Tops, Bottoms, Sets"

    def handle(self, *args, **options):
        order = {'tops': 0, 'bottoms': 1, 'sets': 2}
        for slug, pos in order.items():
            updated = Category.objects.filter(slug=slug).update(display_order=pos)
            if updated:
                self.stdout.write(f"  {slug} → {pos}")

        self.stdout.write(self.style.SUCCESS("Category order updated"))
        for c in Category.objects.order_by('display_order', 'name'):
            self.stdout.write(f"  {c.display_order}: {c.name}")
