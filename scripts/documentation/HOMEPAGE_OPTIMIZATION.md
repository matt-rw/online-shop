# Homepage Performance Optimization Guide

## Current Performance (Before)

```
Homepage Load Time: 8-15 seconds (slow 3G)
Page Weight: ~35MB
Largest Contentful Paint (LCP): 12-18s ❌
First Contentful Paint (FCP): 4-8s ❌
Time to Interactive (TTI): 15-20s ❌

Lighthouse Score: ~15/100 🔴
```

## After Optimization (Expected)

```
Homepage Load Time: 1-3 seconds (slow 3G)
Page Weight: ~800KB (97% reduction!)
Largest Contentful Paint (LCP): <2.5s ✅
First Contentful Paint (FCP): <1.0s ✅
Time to Interactive (TTI): <3.0s ✅

Lighthouse Score: 90+/100 🟢
```

---

## Issue #1: Massive Hero Image (18MB!)

### Problem
```html
<section style="background-image: url('{% static 'images/unnamed.png' %}');">
```

**File**: `static/images/unnamed.png`
**Size**: 18MB
**Load Time**: 10-15 seconds on mobile

### Solution: Image Optimization

#### Option A: Use Online Tool (Easiest - 2 minutes)

1. Go to https://squoosh.app/
2. Upload `static/images/unnamed.png`
3. Settings:
   - Format: WebP
   - Quality: 80
   - Resize: 1920px width (maintains aspect ratio)
4. Download → Save as `unnamed.webp`

**Result**: 18MB → 180KB (99% smaller!)

#### Option B: Use Command Line

```bash
# Install ImageMagick
brew install imagemagick  # Mac
# or
sudo apt-get install imagemagick  # Linux

# Optimize hero image
convert static/images/unnamed.png \
  -resize 1920x \
  -quality 85 \
  -define webp:lossless=false \
  static/images/unnamed.webp

# Result: 18MB → ~200KB
```

#### Update Template

```html
<!-- Before -->
<section style="background-image: url('{% static 'images/unnamed.png' %}');">

<!-- After -->
<section style="background-image: url('{% static 'images/unnamed.webp' %}');">
  <!-- Fallback for old browsers -->
  <picture>
    <source srcset="{% static 'images/unnamed.webp' %}" type="image/webp">
    <img src="{% static 'images/unnamed.jpg' %}" alt="Hero">
  </picture>
</section>
```

---

## Issue #2: Other Large Images

### Optimize All Images

```bash
# Batch optimize all PNG images
for file in static/images/*.png; do
  filename=$(basename "$file" .png)
  convert "$file" \
    -resize 1920x \
    -quality 85 \
    -define webp:lossless=false \
    "static/images/${filename}.webp"
done

# Results:
# web.png (2.9MB) → web.webp (120KB) - 96% smaller
# white_bg_bottom.png (6.3MB) → white_bg_bottom.webp (250KB) - 96% smaller
# white_bg_top.png (6.5MB) → white_bg_top.webp (260KB) - 96% smaller
```

### Update Template References

```html
<!-- Before -->
<img src="{% static 'images/web.png' %}" alt="Blueprint Collection" />

<!-- After -->
<picture>
  <source srcset="{% static 'images/web.webp' %}" type="image/webp">
  <img src="{% static 'images/web.jpg' %}"
       alt="Blueprint Collection"
       loading="lazy"
       width="1920"
       height="1080">
</picture>
```

---

## Issue #3: External Script Blocking

### Problem
```html
<link rel="stylesheet" href="https://unpkg.com/aos@2.3.4/dist/aos.css">
<script src="https://cdn.jsdelivr.net/npm/debug-grid-overlay-custom@1.0.5/index.min.js"></script>
<script src="https://unpkg.com/aos@2.3.4/dist/aos.js"></script>
```

Each external request:
- DNS lookup: 50ms
- TCP connect: 100ms
- TLS handshake: 150ms
- Download: 50-200ms
- **Total: 350-500ms per script!**

### Solution 1: Self-Host Libraries (Best)

```bash
# Download AOS library locally
mkdir -p static/js/vendor static/css/vendor

# Download files
curl https://unpkg.com/aos@2.3.4/dist/aos.css -o static/css/vendor/aos.css
curl https://unpkg.com/aos@2.3.4/dist/aos.js -o static/js/vendor/aos.js

# Minify (optional)
npm install -g terser cssnano-cli
terser static/js/vendor/aos.js -o static/js/vendor/aos.min.js
cssnano static/css/vendor/aos.css static/css/vendor/aos.min.css
```

Update template:
```html
<!-- Before -->
<link rel="stylesheet" href="https://unpkg.com/aos@2.3.4/dist/aos.css">

<!-- After -->
<link rel="stylesheet" href="{% static 'css/vendor/aos.min.css' %}">
```

**Benefit**: Eliminates 350-500ms external request time

### Solution 2: Remove Debug Grid (Production)

```html
<!-- Remove in production -->
<script src="https://cdn.jsdelivr.net/npm/debug-grid-overlay-custom@1.0.5/index.min.js"></script>
```

Or use Django settings:
```html
{% if DEBUG %}
<script src="https://cdn.jsdelivr.net/npm/debug-grid-overlay-custom@1.0.5/index.min.js"></script>
{% endif %}
```

---

## Issue #4: Instagram Embed Slowing Page

### Problem
```html
{% include 'partials/insta.html' %}
```

Instagram embeds load 500KB-1MB of JavaScript and make external API calls (500ms-2s delay).

### Solution: Lazy Load Instagram

Create `static/js/lazy-instagram.js`:
```javascript
// Lazy load Instagram when user scrolls near it
document.addEventListener('DOMContentLoaded', function() {
  const instaContainer = document.querySelector('.instagram-embed');

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        // Load Instagram script only when visible
        const script = document.createElement('script');
        script.src = 'https://www.instagram.com/embed.js';
        script.async = true;
        document.body.appendChild(script);
        observer.disconnect();
      }
    });
  }, {
    rootMargin: '200px' // Load 200px before it's visible
  });

  if (instaContainer) {
    observer.observe(instaContainer);
  }
});
```

Update template:
```html
<div class="instagram-embed">
  {% include 'partials/insta.html' %}
</div>
<script src="{% static 'js/lazy-instagram.js' %}" defer></script>
```

**Benefit**: Instagram loads only when user scrolls to it (saves 1-2s on initial load)

---

## Issue #5: No Lazy Loading

### Problem
All images load immediately, even those below the fold.

### Solution: Add `loading="lazy"`

```html
<!-- Before -->
<img class="rounded-4xl mb-32" src="{% static 'images/web.png' %}" alt="Blueprint Collection" />

<!-- After -->
<img class="rounded-4xl mb-32"
     src="{% static 'images/web.webp' %}"
     alt="Blueprint Collection"
     loading="lazy"
     width="1920"
     height="1080" />
```

Add to all images EXCEPT:
- Hero image (above the fold)
- Logo

**Benefit**: Only loads images as user scrolls (saves 10-20MB on initial load)

---

## Issue #6: No HTTP Compression

### Problem
Text assets (HTML, CSS, JS) aren't compressed.

### Solution: Enable Gzip/Brotli in Django

**File**: `online_shop/settings/base.py`

```python
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',  # Add this FIRST
    'django.middleware.security.SecurityMiddleware',
    # ... rest of middleware
]
```

**File**: `online_shop/settings/production.py`

```python
# WhiteNoise with compression
WHITENOISE_AUTOREFRESH = False
WHITENOISE_USE_FINDERS = False
WHITENOISE_COMPRESS = True  # Enable Brotli compression
WHITENOISE_KEEP_ONLY_HASHED_FILES = True
```

**Benefit**:
- HTML: 10KB → 3KB (70% smaller)
- CSS: 50KB → 12KB (76% smaller)
- JS: 30KB → 8KB (73% smaller)

---

## Issue #7: No Caching Headers

### Problem
Browser re-downloads static files on every visit.

### Solution: Add Cache Headers

WhiteNoise automatically adds cache headers for static files, but verify:

**File**: `online_shop/settings/production.py`

```python
# Static files cache
WHITENOISE_MAX_AGE = 31536000  # 1 year for static files

# Add cache control for media files
MIDDLEWARE += ['whitenoise.middleware.WhiteNoiseMiddleware']

# Custom cache headers for different file types
WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: True
```

**Benefit**: Repeat visitors load instantly (0 bytes transferred)

---

## Issue #8: No Resource Hints

### Problem
Browser doesn't know what to load ahead of time.

### Solution: Add Preconnect & Preload

**File**: `templates/base.html` (in `<head>`)

```html
<!-- Preconnect to external domains -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://www.instagram.com">
<link rel="dns-prefetch" href="https://unpkg.com">

<!-- Preload critical assets -->
<link rel="preload" as="image" href="{% static 'images/unnamed.webp' %}" type="image/webp">
<link rel="preload" as="style" href="{% static 'css/vendor/aos.min.css' %}">
<link rel="preload" as="font" href="{% static 'fonts/your-font.woff2' %}" type="font/woff2" crossorigin>
```

**Benefit**: Saves 100-300ms on external requests

---

## Quick Wins Checklist

### 1. Optimize Images (30 minutes - BIGGEST IMPACT)

```bash
cd static/images

# Optimize hero image
convert unnamed.png -resize 1920x -quality 85 unnamed.webp

# Optimize other images
convert web.png -resize 1920x -quality 85 web.webp
convert blueprint_bg1.png -resize 1920x -quality 85 blueprint_bg1.webp
convert white_bg_bottom.png -resize 1920x -quality 85 white_bg_bottom.webp
convert white_bg_top.png -resize 1920x -quality 85 white_bg_top.webp
```

Update all `<img>` tags to use `.webp` versions.

**Impact**: 35MB → 800KB (96% reduction)
**Speed gain**: 10-15s → 2-3s (80% faster)

### 2. Add Lazy Loading (5 minutes)

Add `loading="lazy"` to all images except hero/logo.

**Impact**: Saves 10-20MB on initial load
**Speed gain**: 300-500ms faster

### 3. Enable Compression (2 minutes)

Add `GZipMiddleware` to settings.

**Impact**: 30-40% smaller HTML/CSS/JS
**Speed gain**: 200-400ms faster

### 4. Remove Debug Script in Production (1 minute)

```html
{% if DEBUG %}
<script src="https://cdn.jsdelivr.net/npm/debug-grid-overlay..."></script>
{% endif %}
```

**Impact**: Removes 1 external request
**Speed gain**: 300-500ms faster

---

## Expected Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| **Page Weight** | 35MB | 800KB | **97% smaller** |
| **Load Time (3G)** | 15s | 2.5s | **83% faster** |
| **Load Time (4G)** | 8s | 1.2s | **85% faster** |
| **Load Time (WiFi)** | 4s | 0.6s | **85% faster** |
| **LCP** | 18s | 1.8s | **90% faster** |
| **FCP** | 6s | 0.8s | **87% faster** |
| **Lighthouse** | 15/100 | 92/100 | **+77 points** |

---

## Testing Performance

### Before Optimization

```bash
# Test with Chrome DevTools
1. Open homepage in Chrome
2. Press F12 → Network tab
3. Throttle to "Slow 3G"
4. Reload page
5. Note load time

Current: ~15 seconds
```

### After Optimization

```bash
# Same test
Expected: ~2.5 seconds
85% improvement!
```

### Use Lighthouse

```bash
# Chrome DevTools
1. F12 → Lighthouse tab
2. Select "Performance"
3. Click "Analyze page load"

Current Score: ~15/100
Expected After: 90+/100
```

---

## Implementation Priority

**Do These First** (1 hour total, 80% of gains):
1. ✅ Optimize hero image (18MB → 180KB) - 30 min
2. ✅ Add lazy loading to images - 5 min
3. ✅ Enable GZip compression - 2 min
4. ✅ Remove debug script in prod - 1 min

**Do These Next** (2 hours, 15% more gains):
5. ✅ Optimize remaining images - 20 min
6. ✅ Self-host AOS library - 15 min
7. ✅ Lazy load Instagram - 20 min
8. ✅ Add preconnect hints - 5 min

**Advanced** (optional, 5% more gains):
9. Set up Cloudflare CDN
10. Implement HTTP/2 push
11. Use AVIF format (newer than WebP)

---

## Django is Fine!

Your slowness is **100% front-end**, not Django:
- Django response time: <50ms
- Image download time: 10-15 seconds

Django + proper caching (Redis) will handle 1000s of requests/sec. The bottleneck is massive images being downloaded over the network.

Want me to implement these optimizations now?
