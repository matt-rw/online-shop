from django.core.management.base import BaseCommand

from shop.models.product import Size


SIZE_ORDER = {
    'XXS': 0, 'XS': 1, 'S': 2, 'M': 3, 'L': 4, 'XL': 5,
    'XXL': 6, '2XL': 6, 'XXXL': 7, '3XL': 7,
}


class Command(BaseCommand):
    help = "Set display order for sizes (XS, S, M, L, XL, XXL)"

    def handle(self, *args, **options):
        for size in Size.objects.all():
            new_order = SIZE_ORDER.get(size.code.upper(), 99)
            if size.display_order != new_order:
                size.display_order = new_order
                size.save(update_fields=["display_order"])
                self.stdout.write(f"  {size.code}: {new_order}")
        self.stdout.write(self.style.SUCCESS("Size display order set."))
