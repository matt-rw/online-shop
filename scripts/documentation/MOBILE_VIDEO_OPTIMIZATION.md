# Mobile Video Optimization Guide

## Strategy: Responsive Video Delivery

**Goal:** Optimize video for mobile devices while keeping original quality for desktop.

**Approach:**
- Mobile/Tablet (≤768px): Serve optimized 720p version (~1-2MB)
- Desktop (>768px): Serve original full-quality version (12MB)

This gives mobile users fast loading while desktop users get the best quality!

---

## Option 1: Use FFmpeg (Command Line) - RECOMMENDED

### Install FFmpeg
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from: https://ffmpeg.org/download.html
```

### Run Optimization Script
```bash
python3 optimize_video_mobile.py
```

This will create `screen_recording_mobile.mp4` (~1-2MB, 720p)

---

## Option 2: Use Online Tool (CloudConvert)

### Step-by-Step:
1. Go to: https://cloudconvert.com/mov-to-mp4

2. Upload: `static/images/screen_recording.mov`

3. **Settings (Click gear icon):**
   - Output format: **MP4**
   - Video codec: **H.264**
   - Quality: **CRF 28**
   - Resolution: **1280x720** (or scale to 720p height)
   - Audio: **Remove audio track**
   - Profile: **Main**
   - Level: **4.0**
   - Advanced: Check "**Fast Start**" (enables streaming)

4. Click "Convert"

5. Download the result

6. **Rename to:** `screen_recording_mobile.mp4`

7. **Save to:** `static/images/screen_recording_mobile.mp4`

---

## Option 3: Use Handbrake (Desktop App)

### Step-by-Step:
1. Download Handbrake: https://handbrake.fr/

2. Open `static/images/screen_recording.mov`

3. **Settings:**
   - **Preset:** "Fast 720p30"
   - **Format:** MP4
   - **Web Optimized:** ✓ Checked (enables fast start)

4. **Video Tab:**
   - Encoder: H.264
   - Quality: RF 28
   - Framerate: Same as source

5. **Dimensions Tab:**
   - Resolution: 1280x720 (or height: 720, width: Auto)

6. **Audio Tab:**
   - Remove all audio tracks (not needed)

7. **Save as:** `screen_recording_mobile.mp4`

8. **Output to:** `static/images/screen_recording_mobile.mp4`

---

## Manual FFmpeg Command

If you prefer to run ffmpeg directly:

```bash
ffmpeg -i static/images/screen_recording.mov \
  -vf "scale=-2:720" \
  -c:v libx264 \
  -crf 28 \
  -preset slow \
  -profile:v main \
  -level 4.0 \
  -movflags +faststart \
  -an \
  static/images/screen_recording_mobile.mp4
```

**Command breakdown:**
- `-vf "scale=-2:720"` - Scale to 720p height, auto-calculate width (maintains aspect ratio)
- `-c:v libx264` - Use H.264 codec (best compatibility)
- `-crf 28` - Quality level (18=best, 51=worst, 28=good balance)
- `-preset slow` - Slower encoding = better compression
- `-profile:v main` - Compatibility profile for mobile devices
- `-level 4.0` - Compatibility level
- `-movflags +faststart` - Enable streaming (load while playing)
- `-an` - Remove audio track

---

## After Creating Mobile Video

### Update HTML Template

Edit `templates/home/home_page.html` at line 649:

**Before:**
```html
<video autoplay muted loop playsinline class="absolute inset-0 w-full h-full object-cover opacity-30">
  <source src="{% static 'images/screen_recording.mov' %}" type="video/mp4">
</video>
```

**After:**
```html
<video autoplay muted loop playsinline class="absolute inset-0 w-full h-full object-cover opacity-30">
  <!-- Mobile: Optimized 720p version -->
  <source src="{% static 'images/screen_recording_mobile.mp4' %}"
          type="video/mp4"
          media="(max-width: 768px)">
  <!-- Desktop/Tablet: Original quality -->
  <source src="{% static 'images/screen_recording.mov' %}"
          type="video/mp4">
</video>
```

---

## Expected Results

### Mobile Version (720p, CRF 28)
- **File size:** 1-2 MB
- **Resolution:** 1280x720
- **Quality:** Very good (suitable for mobile screens)
- **Load time (3G):** 2-3 seconds
- **Load time (4G):** <1 second

### Desktop Version (Original)
- **File size:** 12 MB
- **Resolution:** Original (likely 1920x1080 or higher)
- **Quality:** Excellent
- **Load time (WiFi):** 2-3 seconds
- **Load time (4G):** 3-5 seconds

---

## Quality Comparison

### Mobile (720p)
- Perfect for screens ≤768px wide
- Indistinguishable from original on mobile
- 85-90% smaller file size
- Much faster loading

### Desktop (Original)
- Best quality for large screens
- No compression artifacts
- Crisp details on high-res monitors
- Worth the extra load time on fast connections

---

## Browser Support

The `media` attribute on `<source>` is supported by:
- ✅ Chrome/Edge (all versions)
- ✅ Firefox (all versions)
- ✅ Safari (all versions)
- ✅ Mobile browsers (iOS, Android)

**Fallback:** Browsers that don't support media queries will use the first compatible source (mobile version).

---

## Testing

After implementing:

1. **Test on Mobile:**
   - Open Chrome DevTools
   - Toggle device toolbar (Ctrl+Shift+M)
   - Set viewport to iPhone/Android
   - Check Network tab - should load mobile.mp4
   - Verify video quality looks good

2. **Test on Desktop:**
   - Set viewport to desktop size (>768px)
   - Check Network tab - should load original .mov
   - Verify video quality is excellent

3. **Check File Sizes:**
   ```bash
   ls -lh static/images/screen_recording*
   ```
   Should see:
   - screen_recording.mov: 12M
   - screen_recording_mobile.mp4: ~1-2M

---

## Performance Impact

### Before (All Devices Load 12MB)
- Mobile load time: 8-15 seconds (3G)
- Desktop load time: 2-3 seconds (WiFi)
- Mobile data usage: 12MB

### After (Responsive Loading)
- Mobile load time: 2-3 seconds (3G) ✅
- Desktop load time: 2-3 seconds (WiFi) ✅
- Mobile data usage: 1-2MB ✅

**Result:** 85% faster on mobile, no quality loss on desktop! 🚀

---

## Alternative: WebM Format (Optional)

For even better compression, you can also create a WebM version:

```bash
ffmpeg -i static/images/screen_recording.mov \
  -vf "scale=-2:720" \
  -c:v libvpx-vp9 \
  -crf 35 \
  -b:v 0 \
  -an \
  static/images/screen_recording_mobile.webm
```

Then use:
```html
<video autoplay muted loop playsinline ...>
  <!-- Mobile: WebM (best compression) -->
  <source src="{% static 'images/screen_recording_mobile.webm' %}"
          type="video/webm"
          media="(max-width: 768px)">
  <!-- Mobile: MP4 (fallback) -->
  <source src="{% static 'images/screen_recording_mobile.mp4' %}"
          type="video/mp4"
          media="(max-width: 768px)">
  <!-- Desktop: Original -->
  <source src="{% static 'images/screen_recording.mov' %}"
          type="video/mp4">
</video>
```

---

## Need Help?

If you encounter issues:

1. **FFmpeg not installed:**
   - Use online tool (CloudConvert) or Handbrake
   - Both are free and user-friendly

2. **Video quality not good enough:**
   - Lower CRF value (try 24-26 instead of 28)
   - Increase resolution to 1080p instead of 720p

3. **File size too large:**
   - Increase CRF value (try 30-32 instead of 28)
   - Keep resolution at 720p
   - Remove audio track if present

4. **Video won't play:**
   - Check file extension matches type attribute
   - Verify file uploaded to correct location
   - Clear browser cache and test again

---

## Summary

✅ **Best Practice:** Create separate mobile and desktop versions

✅ **Mobile:** 720p, CRF 28, ~1-2MB

✅ **Desktop:** Original quality, 12MB

✅ **Result:** Fast mobile + beautiful desktop

This approach gives you the best of both worlds! 🎯
