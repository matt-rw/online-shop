#!/usr/bin/env python3
"""
Add a white circle border around the blueprint logo
"""
from PIL import Image, ImageDraw

def add_white_circle(input_path, output_path, circle_thickness=3):
    """
    Add a white circle around the logo

    Args:
        input_path: Path to input image (cropped logo)
        output_path: Path to output image
        circle_thickness: Thickness of the white circle border
    """
    print(f"📸 Opening: {input_path}")

    with Image.open(input_path) as img:
        # Convert to RGBA to work with transparency
        if img.mode != 'RGBA':
            img = img.convert('RGBA')

        width, height = img.size
        print(f"   Original size: {width}x{height}")

        # Calculate circle diameter (use the larger dimension)
        diameter = max(width, height)

        # Add some padding around the circle
        padding = 10
        canvas_size = diameter + padding * 2

        # Create a new square canvas with black background
        canvas = Image.new('RGBA', (canvas_size, canvas_size), (0, 0, 0, 255))

        # Draw white circle
        draw = ImageDraw.Draw(canvas)
        circle_left = padding
        circle_top = padding
        circle_right = padding + diameter
        circle_bottom = padding + diameter

        # Draw filled white circle
        draw.ellipse(
            [(circle_left, circle_top), (circle_right, circle_bottom)],
            fill=(255, 255, 255, 255)
        )

        # Draw white circle outline for extra thickness
        for i in range(circle_thickness):
            draw.ellipse(
                [(circle_left + i, circle_top + i), (circle_right - i, circle_bottom - i)],
                outline=(255, 255, 255, 255),
                width=1
            )

        # Create black circle inside to make it just a ring
        inner_padding = circle_thickness
        draw.ellipse(
            [(circle_left + inner_padding, circle_top + inner_padding),
             (circle_right - inner_padding, circle_bottom - inner_padding)],
            fill=(0, 0, 0, 255)
        )

        # Calculate position to center the original logo
        x_offset = (canvas_size - width) // 2
        y_offset = (canvas_size - height) // 2

        # Paste the original logo on top
        canvas.paste(img, (x_offset, y_offset), img)

        # Convert back to RGB
        final = Image.new('RGB', canvas.size, (0, 0, 0))
        final.paste(canvas, (0, 0))

        print(f"   New size: {final.size}")

        # Save
        final.save(output_path, quality=95)
        print(f"   ✅ Saved: {output_path}")

if __name__ == "__main__":
    add_white_circle(
        "static/images/blueprint_b_cropped.jpg",
        "static/images/blueprint_b_circle.jpg",
        circle_thickness=3
    )
