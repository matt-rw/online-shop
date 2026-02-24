"""
Image optimization utilities for uploaded images.
Automatically resizes, compresses, and converts images to WebP.
"""
import io
import uuid
from PIL import Image, ExifTags

# High quality settings
MAX_DIMENSION = 2048  # Max width or height (good for retina)
WEBP_QUALITY = 90  # High quality WebP
JPEG_QUALITY = 90  # Fallback JPEG quality


def optimize_image(image_file, filename=None, max_dimension=MAX_DIMENSION, quality=WEBP_QUALITY):
    """
    Optimize an uploaded image file.

    - Resizes to max_dimension if larger
    - Converts to WebP for better compression
    - Strips EXIF data (privacy + smaller file)
    - Returns optimized image bytes and new filename

    Args:
        image_file: File-like object or path to image
        filename: Original filename (used to generate new name)
        max_dimension: Max width or height in pixels
        quality: Output quality (1-100)

    Returns:
        tuple: (optimized_bytes, new_filename, content_type)
    """
    # Open image
    img = Image.open(image_file)

    # Handle EXIF orientation before stripping
    img = _fix_orientation(img)

    # Convert to RGB if necessary (WebP doesn't support all modes)
    if img.mode in ('RGBA', 'LA', 'P'):
        # Preserve transparency
        if img.mode == 'P':
            img = img.convert('RGBA')
        background = Image.new('RGBA', img.size, (255, 255, 255, 0))
        if img.mode == 'RGBA':
            background.paste(img, mask=img.split()[3])
        else:
            background.paste(img)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if larger than max dimension
    original_size = max(img.size)
    if original_size > max_dimension:
        ratio = max_dimension / original_size
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Save as WebP
    output = io.BytesIO()

    # Check if image has transparency
    has_alpha = img.mode == 'RGBA'

    if has_alpha:
        img.save(output, format='WEBP', quality=quality, method=6)
    else:
        # Convert to RGB for non-transparent images
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(output, format='WEBP', quality=quality, method=6)

    output.seek(0)

    # Generate new filename
    if filename:
        base_name = filename.rsplit('.', 1)[0]
        new_filename = f"{base_name}_{uuid.uuid4().hex[:8]}.webp"
    else:
        new_filename = f"{uuid.uuid4().hex}.webp"

    return output.getvalue(), new_filename, 'image/webp'


def optimize_image_keep_format(image_file, filename=None, max_dimension=MAX_DIMENSION, quality=JPEG_QUALITY):
    """
    Optimize an image while keeping its original format.
    Use this when WebP isn't suitable (e.g., email compatibility).

    Returns:
        tuple: (optimized_bytes, new_filename, content_type)
    """
    img = Image.open(image_file)
    img = _fix_orientation(img)

    # Determine format
    original_format = img.format or 'JPEG'
    if original_format.upper() == 'JPG':
        original_format = 'JPEG'

    # Convert mode if needed
    if original_format == 'JPEG' and img.mode != 'RGB':
        img = img.convert('RGB')

    # Resize if needed
    original_size = max(img.size)
    if original_size > max_dimension:
        ratio = max_dimension / original_size
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # Save
    output = io.BytesIO()

    if original_format == 'JPEG':
        img.save(output, format='JPEG', quality=quality, optimize=True)
        ext = 'jpg'
        content_type = 'image/jpeg'
    elif original_format == 'PNG':
        img.save(output, format='PNG', optimize=True)
        ext = 'png'
        content_type = 'image/png'
    else:
        # Default to JPEG
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(output, format='JPEG', quality=quality, optimize=True)
        ext = 'jpg'
        content_type = 'image/jpeg'

    output.seek(0)

    # Generate filename
    if filename:
        base_name = filename.rsplit('.', 1)[0]
        new_filename = f"{base_name}_{uuid.uuid4().hex[:8]}.{ext}"
    else:
        new_filename = f"{uuid.uuid4().hex}.{ext}"

    return output.getvalue(), new_filename, content_type


def _fix_orientation(img):
    """Fix image orientation based on EXIF data."""
    try:
        exif = img._getexif()
        if exif is None:
            return img

        orientation_key = None
        for key, val in ExifTags.TAGS.items():
            if val == 'Orientation':
                orientation_key = key
                break

        if orientation_key is None or orientation_key not in exif:
            return img

        orientation = exif[orientation_key]

        if orientation == 2:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 3:
            img = img.rotate(180)
        elif orientation == 4:
            img = img.transpose(Image.FLIP_TOP_BOTTOM)
        elif orientation == 5:
            img = img.rotate(-90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 6:
            img = img.rotate(-90, expand=True)
        elif orientation == 7:
            img = img.rotate(90, expand=True).transpose(Image.FLIP_LEFT_RIGHT)
        elif orientation == 8:
            img = img.rotate(90, expand=True)
    except (AttributeError, KeyError, IndexError, TypeError):
        pass

    return img


def get_image_dimensions(image_file):
    """Get image dimensions without fully loading it."""
    img = Image.open(image_file)
    return img.size


def estimate_savings(original_size, optimized_size):
    """Calculate percentage savings from optimization."""
    if original_size == 0:
        return 0
    return round((1 - optimized_size / original_size) * 100, 1)
