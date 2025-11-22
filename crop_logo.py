#!/usr/bin/env python3
"""
Crop the blueprint_b.jpg logo to remove excess black border
"""
from PIL import Image

def crop_logo_smart(input_path, output_path, padding=5):
    """
    Crop black borders from logo by finding white content

    Args:
        input_path: Path to input image
        output_path: Path to output image
        padding: Pixels of padding to add around the cropped content
    """
    print(f"📸 Opening: {input_path}")

    with Image.open(input_path) as img:
        # Convert to grayscale for easier analysis
        gray = img.convert('L')
        width, height = gray.size

        print(f"   Original size: {gray.size}")

        # Find the bounding box of non-black content
        # Threshold: any pixel brighter than 50 (out of 255)
        threshold = 50

        min_x, min_y = width, height
        max_x, max_y = 0, 0

        # Scan the image to find bright pixels
        pixels = gray.load()
        for y in range(height):
            for x in range(width):
                if pixels[x, y] > threshold:
                    min_x = min(min_x, x)
                    max_x = max(max_x, x)
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)

        if min_x < width and min_y < height:
            # Add padding
            left = max(0, min_x - padding)
            top = max(0, min_y - padding)
            right = min(width, max_x + 1 + padding)
            bottom = min(height, max_y + 1 + padding)

            print(f"   Content bbox: ({left}, {top}, {right}, {bottom})")

            # Crop to content
            cropped = img.crop((left, top, right, bottom))
            print(f"   Cropped size: {cropped.size}")

            # Save the cropped image
            cropped.save(output_path, quality=95)
            print(f"   ✅ Saved: {output_path}")
        else:
            print("   ⚠️  No content found!")

if __name__ == "__main__":
    crop_logo_smart(
        "static/images/blueprint_b.jpg",
        "static/images/blueprint_b_cropped.jpg",
        padding=5  # Small padding around the hexagon
    )
