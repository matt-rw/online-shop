# Video Optimization Instructions

## Current Status
- **Original video**: `static/images/screen_recording.mov` (12MB)
- **Target size**: <2MB with high quality
- **Original backed up**: `static/images/originals/video/screen_recording.mov` ✓

## Why This Matters
A 12MB video will:
- Cause 5-10 second delays on mobile devices
- Use significant data (bad for users on limited plans)
- Hurt SEO rankings (poor Core Web Vitals scores)
- Reduce conversion rates (users leave before page loads)

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

### Run Optimization
```bash
# From project root directory
./optimize_video.sh
```

This will create:
- `screen_recording.mp4` (~1-2MB, excellent quality)
- `screen_recording.webm` (~800KB-1.5MB, better compression)

## Option 2: Use Online Tools

### CloudConvert (Free, No Registration)
1. Go to: https://cloudconvert.com/mov-to-mp4
2. Upload: `static/images/screen_recording.mov`
3. Settings:
   - Output format: MP4
   - Video codec: H.264
   - Quality: High (CRF 28)
   - Resolution: 1920x1080 (or original if smaller)
   - Remove audio track (video is muted anyway)
4. Download optimized video
5. Rename to: `screen_recording.mp4`
6. Save to: `static/images/screen_recording.mp4`

### Handbrake (Desktop App, Free)
1. Download: https://handbrake.fr/
2. Open `screen_recording.mov`
3. Preset: "Web" → "Gmail Medium 5 Minutes 480p30"
4. Video tab:
   - Framerate: Same as source
   - Quality: RF 28 (higher number = smaller file)
   - Encoder: H.264
5. Audio tab: Remove all audio tracks
6. Save as: `screen_recording.mp4`

## Option 3: Use Python (if FFmpeg available)

If you have ffmpeg installed on your system:

```bash
python3 optimize_video_python.py
```

## After Optimization

### 1. Update HTML Template
Edit `templates/home/home_page.html` line 649:

**Before:**
```html
<video autoplay muted loop playsinline ...>
  <source src="{% static 'images/screen_recording.mov' %}" type="video/mp4">
</video>
```

**After:**
```html
<video autoplay muted loop playsinline ...>
  <source src="{% static 'images/screen_recording.webm' %}" type="video/webm">
  <source src="{% static 'images/screen_recording.mp4' %}" type="video/mp4">
</video>
```

### 2. Test in Browser
1. Run Django server: `python manage.py runserver`
2. Open homepage in browser
3. Check video plays correctly
4. Verify video quality looks good

### 3. Verify File Sizes
```bash
ls -lh static/images/screen_recording.*
```

Expected results:
- `.mov` (original): 12MB
- `.mp4` (optimized): 1-2MB
- `.webm` (optional): 800KB-1.5MB

### 4. Check Loading Performance
Use Chrome DevTools:
1. Open homepage
2. F12 → Network tab
3. Refresh page
4. Check video file size and load time
5. Should be <2 seconds on fast 3G

## Technical Details

### FFmpeg Command Breakdown
```bash
ffmpeg -i screen_recording.mov \
  -vcodec libx264 \        # H.264 codec (best compatibility)
  -crf 28 \                 # Quality level (18=highest, 51=lowest, 28=good balance)
  -preset slow \            # Slower encoding = better compression
  -vf "scale=1920:1080" \   # Resize if larger than 1080p
  -movflags +faststart \    # Enable streaming (load while playing)
  -an \                     # Remove audio (not needed)
  screen_recording.mp4
```

### Quality Levels (CRF)
- **18-23**: Visually lossless, large file size
- **24-28**: High quality, good compression (RECOMMENDED)
- **29-35**: Medium quality, smaller files
- **36+**: Low quality, not recommended

### WebM vs MP4
- **MP4 (H.264)**: Better compatibility, all browsers
- **WebM (VP9)**: Better compression (30-50% smaller), modern browsers only
- **Recommendation**: Use both, browsers will pick best supported format

## Estimated Results

**Original (MOV):**
- Size: 12.0 MB
- Load time (3G): ~20 seconds
- Load time (4G): ~8 seconds

**Optimized (MP4, CRF 28):**
- Size: 1.5-2.0 MB
- Load time (3G): ~2-3 seconds
- Load time (4G): <1 second
- Quality: 95% visual fidelity

**Optimized (WebM, CRF 35):**
- Size: 800KB-1.2 MB
- Load time (3G): ~1-2 seconds
- Load time (4G): <1 second
- Quality: 93% visual fidelity

## Need Help?

If you run into issues:
1. Check that ffmpeg is properly installed: `ffmpeg -version`
2. Verify input file exists: `ls -lh static/images/screen_recording.mov`
3. Check file permissions: `chmod +x optimize_video.sh`
4. Try online tools as backup option

## Status

- [x] Original video backed up
- [ ] Video optimized to MP4
- [ ] WebM version created (optional)
- [ ] HTML template updated
- [ ] Video tested in browser
- [ ] Original .mov removed (optional, after testing)
