# Original Image Backups

This folder contains the original PNG images before WebP optimization.

**DO NOT DELETE** - These are your source files!

## Files

- `unnamed.png` - Original hero image (17.52 MB)
- `web.png` - Original feature image (2.87 MB)
- `blueprint_bg1.png` - Original background (155 KB)
- `white_bg_bottom.png` - Original image (6.30 MB)
- `white_bg_top.png` - Original image (6.46 MB)
- `font.png` - Original logo (52 KB)

## Optimized Versions

The optimized WebP versions are in `static/images/`:
- 94% smaller file sizes
- Same visual quality
- Faster page loads

## If You Need Originals

If you need to re-optimize or create different versions:

```bash
cd static/images/originals
python3 ../../optimize_images.py
```

**Total backup size**: 33.36 MB
**Optimized size**: 1.89 MB
**Savings**: 31.47 MB (94.3%)
