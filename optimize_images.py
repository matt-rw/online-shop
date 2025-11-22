#!/usr/bin/env python3
"""
Image Optimization Script
Converts large PNG images to optimized WebP format for faster page loads.
"""
import os
from pathlib import Path

from PIL import Image


def optimize_image(input_path, output_path=None, max_width=1920, quality=85):
    """
    Optimize an image by resizing and converting to WebP.

    Args:
        input_path: Path to input image
        output_path: Path to output image (defaults to same name with .webp)
        max_width: Maximum width to resize to (maintains aspect ratio)
        quality: WebP quality (0-100, 85 is good balance)

    Returns:
        Tuple of (original_size, new_size, savings_percent)
    """
    if output_path is None:
        output_path = str(Path(input_path).with_suffix(".webp"))

    # Get original file size
    original_size = os.path.getsize(input_path)

    # Open and process image
    print(f"\n📸 Processing: {input_path}")
    print(f"   Original size: {original_size / 1024 / 1024:.2f} MB")

    with Image.open(input_path) as img:
        # Convert RGBA to RGB if necessary (WebP doesn't support transparency well)
        if img.mode in ("RGBA", "LA", "P"):
            # Create a white background
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if needed
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            # Use LANCZOS for older Pillow versions (Image.ANTIALIAS is deprecated)
            try:
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            except AttributeError:
                img = img.resize((max_width, new_height), Image.LANCZOS)
            print(f"   Resized: {img.width}x{img.height}")

        # Save as WebP
        img.save(output_path, "WebP", quality=quality, method=6)

    # Get new file size
    new_size = os.path.getsize(output_path)
    savings = ((original_size - new_size) / original_size) * 100

    print(f"   New size: {new_size / 1024 / 1024:.2f} MB")
    print(f"   💾 Saved: {savings:.1f}% ({(original_size - new_size) / 1024 / 1024:.2f} MB)")
    print(f"   ✅ Created: {output_path}")

    return original_size, new_size, savings


def main():
    """Optimize all images in static/images/"""
    images_dir = Path("static/images")

    # Images to optimize (the large ones from the homepage)
    images_to_optimize = [
        "unnamed.png",  # Hero image - 18MB
        "web.png",  # Feature image - 2.9MB
        "blueprint_bg1.png",  # Background - 155KB
        "white_bg_bottom.png",  # 6.3MB
        "white_bg_top.png",  # 6.5MB
        "font.png",  # Logo - 52KB
    ]

    total_original = 0
    total_new = 0
    optimized_count = 0

    print("=" * 60)
    print("🖼️  IMAGE OPTIMIZATION STARTING")
    print("=" * 60)

    for image_name in images_to_optimize:
        input_path = images_dir / image_name

        if not input_path.exists():
            print(f"\n⚠️  Skipping {image_name} (not found)")
            continue

        try:
            original, new, savings = optimize_image(str(input_path), max_width=1920, quality=85)
            total_original += original
            total_new += new
            optimized_count += 1
        except Exception as e:
            print(f"\n❌ Error processing {image_name}: {e}")

    # Print summary
    print("\n" + "=" * 60)
    print("📊 OPTIMIZATION SUMMARY")
    print("=" * 60)
    print(f"Images optimized: {optimized_count}")
    print(f"Original total size: {total_original / 1024 / 1024:.2f} MB")
    print(f"New total size: {total_new / 1024 / 1024:.2f} MB")
    print(f"Total savings: {((total_original - total_new) / total_original) * 100:.1f}%")
    print(f"Saved: {(total_original - total_new) / 1024 / 1024:.2f} MB")
    print("=" * 60)
    print("\n✨ Optimization complete!")
    print("\n📝 Next steps:")
    print("   1. Update templates to use .webp images")
    print("   2. Add lazy loading attributes")
    print("   3. Test the homepage")
    print("   4. Delete old .png files (optional, after testing)")


if __name__ == "__main__":
    main()
