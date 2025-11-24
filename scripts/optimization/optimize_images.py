#!/usr/bin/env python3
"""
Optimize images for production while maintaining high quality.
Keeps originals in originals/ directory.
"""
import os
import subprocess
from pathlib import Path
from PIL import Image

def optimize_jpeg_to_webp(input_path, output_path, quality=85):
    """Convert JPEG to WebP with high quality."""
    try:
        img = Image.open(input_path)

        # Resize if too large (max 1920px on longest side)
        max_dimension = 1920
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"  Resized from {Image.open(input_path).size} to {new_size}")

        # Save as WebP with high quality
        img.save(output_path, 'WEBP', quality=quality, method=6)

        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        reduction = (1 - new_size / original_size) * 100

        print(f"✓ {input_path.name}")
        print(f"  {original_size / 1024 / 1024:.2f}MB → {new_size / 1024 / 1024:.2f}MB ({reduction:.1f}% reduction)")

        return True
    except Exception as e:
        print(f"✗ Error processing {input_path}: {e}")
        return False

def optimize_jpeg_inplace(input_path, quality=85, max_dimension=1920):
    """Optimize JPEG in place with high quality."""
    try:
        img = Image.open(input_path)

        # Resize if too large
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            original_size_tuple = img.size
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            print(f"  Resized from {original_size_tuple} to {new_size}")

        # Save optimized
        original_size = os.path.getsize(input_path)
        img.save(input_path, 'JPEG', quality=quality, optimize=True)
        new_size = os.path.getsize(input_path)
        reduction = (1 - new_size / original_size) * 100

        print(f"✓ {input_path.name}")
        print(f"  {original_size / 1024 / 1024:.2f}MB → {new_size / 1024 / 1024:.2f}MB ({reduction:.1f}% reduction)")

        return True
    except Exception as e:
        print(f"✗ Error processing {input_path}: {e}")
        return False

def optimize_png(input_path, quality=85):
    """Optimize PNG by converting to WebP."""
    try:
        output_path = input_path.with_suffix('.webp')
        img = Image.open(input_path)

        # Save as WebP
        img.save(output_path, 'WEBP', quality=quality, method=6)

        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        reduction = (1 - new_size / original_size) * 100

        print(f"✓ {input_path.name} → {output_path.name}")
        print(f"  {original_size / 1024 / 1024:.2f}MB → {new_size / 1024 / 1024:.2f}MB ({reduction:.1f}% reduction)")

        return True
    except Exception as e:
        print(f"✗ Error processing {input_path}: {e}")
        return False

def main():
    base_dir = Path('static/images')

    print("=" * 60)
    print("IMAGE OPTIMIZATION - HIGH QUALITY MODE")
    print("=" * 60)

    # Optimize nature_shots JPEGs
    print("\n1. Optimizing nature_shots/ JPEGs...")
    print("-" * 60)
    nature_shots = base_dir / 'nature_shots'
    for jpeg_file in nature_shots.glob('*.jpeg'):
        optimize_jpeg_inplace(jpeg_file, quality=85, max_dimension=1920)

    # Optimize large PNGs to WebP
    print("\n2. Converting large PNGs to WebP...")
    print("-" * 60)
    large_pngs = [
        base_dir / 'dark_chrome.png',
        base_dir / 'light_chrome.png',
        base_dir / 'blueprint_bg2.png'
    ]
    for png_file in large_pngs:
        if png_file.exists():
            optimize_png(png_file, quality=90)

    print("\n" + "=" * 60)
    print("✓ IMAGE OPTIMIZATION COMPLETE")
    print("=" * 60)
    print("Original files backed up in: static/images/originals/")
    print("\nNext: Run optimize_video.sh to compress the video file")

if __name__ == '__main__':
    main()
