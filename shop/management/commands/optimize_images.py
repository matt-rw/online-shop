"""
Management command to optimize all existing images in the database.
Converts to WebP and compresses for faster page loads.

Usage:
    python manage.py optimize_images          # Dry run (shows what would be optimized)
    python manage.py optimize_images --apply  # Actually optimize images
"""
import base64
import io
from django.core.management.base import BaseCommand
from shop.models import Product, ProductVariant, Bundle
from shop.models.settings import SiteSettings
from shop.utils.image_optimizer import optimize_image


def get_base64_size(data_url):
    """Get approximate size in bytes of a base64 data URL."""
    if not data_url or not data_url.startswith('data:'):
        return 0
    try:
        # Remove the data:image/xxx;base64, prefix
        base64_data = data_url.split(',', 1)[1]
        return len(base64_data) * 3 // 4  # Approximate decoded size
    except (IndexError, ValueError):
        return 0


def is_already_webp(data_url):
    """Check if image is already WebP format."""
    if not data_url:
        return False
    return 'image/webp' in data_url.lower()


def optimize_base64_image(data_url):
    """
    Optimize a base64 data URL image.
    Returns (optimized_data_url, original_size, new_size) or None if failed.
    """
    if not data_url or not data_url.startswith('data:'):
        return None

    try:
        # Decode base64
        header, base64_data = data_url.split(',', 1)
        image_bytes = base64.b64decode(base64_data)
        original_size = len(image_bytes)

        # Optimize
        optimized_bytes, _, content_type = optimize_image(
            io.BytesIO(image_bytes),
            filename="image.jpg"
        )
        new_size = len(optimized_bytes)

        # Encode back to base64
        new_base64 = base64.b64encode(optimized_bytes).decode('utf-8')
        new_data_url = f"data:{content_type};base64,{new_base64}"

        return new_data_url, original_size, new_size
    except Exception as e:
        return None


class Command(BaseCommand):
    help = 'Optimize all existing images in the database to WebP format'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Actually apply optimizations (default is dry run)',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        if apply:
            self.stdout.write(self.style.WARNING('🔧 APPLYING optimizations...\n'))
        else:
            self.stdout.write(self.style.NOTICE('👀 DRY RUN - use --apply to actually optimize\n'))

        total_original = 0
        total_optimized = 0
        images_processed = 0
        images_skipped = 0

        # 1. Product images
        self.stdout.write('\n📦 Processing Products...')
        for product in Product.objects.all():
            if product.images:
                new_images = []
                modified = False
                for img_url in product.images:
                    if is_already_webp(img_url):
                        new_images.append(img_url)
                        images_skipped += 1
                        continue

                    result = optimize_base64_image(img_url)
                    if result:
                        new_url, orig_size, new_size = result
                        total_original += orig_size
                        total_optimized += new_size
                        images_processed += 1
                        savings = (1 - new_size / orig_size) * 100 if orig_size else 0
                        self.stdout.write(f'  ✓ {product.name}: {orig_size//1024}KB → {new_size//1024}KB ({savings:.0f}% saved)')
                        new_images.append(new_url)
                        modified = True
                    else:
                        new_images.append(img_url)

                if modified and apply:
                    product.images = new_images
                    product.save(update_fields=['images'])

        # 2. Product Variant images
        self.stdout.write('\n🎨 Processing Product Variants...')
        for variant in ProductVariant.objects.all():
            if variant.images:
                new_images = []
                modified = False
                for img_url in variant.images:
                    if is_already_webp(img_url):
                        new_images.append(img_url)
                        images_skipped += 1
                        continue

                    result = optimize_base64_image(img_url)
                    if result:
                        new_url, orig_size, new_size = result
                        total_original += orig_size
                        total_optimized += new_size
                        images_processed += 1
                        savings = (1 - new_size / orig_size) * 100 if orig_size else 0
                        self.stdout.write(f'  ✓ {variant.product.name} - {variant.name}: {orig_size//1024}KB → {new_size//1024}KB ({savings:.0f}% saved)')
                        new_images.append(new_url)
                        modified = True
                    else:
                        new_images.append(img_url)

                if modified and apply:
                    variant.images = new_images
                    variant.save(update_fields=['images'])

        # 3. Bundle images
        self.stdout.write('\n🎁 Processing Bundles...')
        for bundle in Bundle.objects.all():
            if bundle.images:
                new_images = []
                modified = False
                for img_url in bundle.images:
                    if is_already_webp(img_url):
                        new_images.append(img_url)
                        images_skipped += 1
                        continue

                    result = optimize_base64_image(img_url)
                    if result:
                        new_url, orig_size, new_size = result
                        total_original += orig_size
                        total_optimized += new_size
                        images_processed += 1
                        savings = (1 - new_size / orig_size) * 100 if orig_size else 0
                        self.stdout.write(f'  ✓ {bundle.name}: {orig_size//1024}KB → {new_size//1024}KB ({savings:.0f}% saved)')
                        new_images.append(new_url)
                        modified = True
                    else:
                        new_images.append(img_url)

                if modified and apply:
                    bundle.images = new_images
                    bundle.save(update_fields=['images'])

        # 4. Site Settings (hero slides & gallery)
        self.stdout.write('\n🖼️ Processing Site Settings...')
        try:
            settings = SiteSettings.objects.first()
            if settings:
                # Hero slides
                if settings.hero_slides:
                    new_slides = []
                    modified = False
                    for slide in settings.hero_slides:
                        img_url = slide.get('image_url', '')
                        if is_already_webp(img_url):
                            new_slides.append(slide)
                            images_skipped += 1
                            continue

                        result = optimize_base64_image(img_url)
                        if result:
                            new_url, orig_size, new_size = result
                            total_original += orig_size
                            total_optimized += new_size
                            images_processed += 1
                            savings = (1 - new_size / orig_size) * 100 if orig_size else 0
                            self.stdout.write(f'  ✓ Hero slide: {orig_size//1024}KB → {new_size//1024}KB ({savings:.0f}% saved)')
                            new_slide = slide.copy()
                            new_slide['image_url'] = new_url
                            new_slides.append(new_slide)
                            modified = True
                        else:
                            new_slides.append(slide)

                    if modified and apply:
                        settings.hero_slides = new_slides
                        settings.save(update_fields=['hero_slides'])

                # Gallery images
                if settings.gallery_images:
                    new_gallery = []
                    modified = False
                    for img in settings.gallery_images:
                        img_url = img.get('image_url', '')
                        if is_already_webp(img_url):
                            new_gallery.append(img)
                            images_skipped += 1
                            continue

                        result = optimize_base64_image(img_url)
                        if result:
                            new_url, orig_size, new_size = result
                            total_original += orig_size
                            total_optimized += new_size
                            images_processed += 1
                            savings = (1 - new_size / orig_size) * 100 if orig_size else 0
                            self.stdout.write(f'  ✓ Gallery image: {orig_size//1024}KB → {new_size//1024}KB ({savings:.0f}% saved)')
                            new_img = img.copy()
                            new_img['image_url'] = new_url
                            new_gallery.append(new_img)
                            modified = True
                        else:
                            new_gallery.append(img)

                    if modified and apply:
                        settings.gallery_images = new_gallery
                        settings.save(update_fields=['gallery_images'])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error processing site settings: {e}'))

        # Summary
        self.stdout.write('\n' + '='*50)
        self.stdout.write(self.style.SUCCESS(f'\n📊 SUMMARY:'))
        self.stdout.write(f'  Images processed: {images_processed}')
        self.stdout.write(f'  Images skipped (already WebP): {images_skipped}')

        if total_original > 0:
            total_savings = (1 - total_optimized / total_original) * 100
            self.stdout.write(f'  Original size: {total_original // 1024 // 1024}MB ({total_original // 1024}KB)')
            self.stdout.write(f'  Optimized size: {total_optimized // 1024 // 1024}MB ({total_optimized // 1024}KB)')
            self.stdout.write(self.style.SUCCESS(f'  Total savings: {total_savings:.0f}%'))

        if not apply and images_processed > 0:
            self.stdout.write(self.style.WARNING('\n⚠️  This was a dry run. Run with --apply to save changes.'))
