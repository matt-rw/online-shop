#!/bin/bash
#
# Video Optimization Script - Run This After Installing ffmpeg
#

echo "=========================================="
echo "VIDEO OPTIMIZATION"
echo "=========================================="
echo ""

# Check if ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "❌ ffmpeg not found. Installing..."
    echo ""
    echo "Run these commands:"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install -y ffmpeg"
    echo ""
    echo "Then run this script again:"
    echo "  bash run_video_optimization.sh"
    exit 1
fi

echo "✓ ffmpeg found"
echo ""

INPUT="static/images/screen_recording.mov"
OUTPUT_MOBILE="static/images/screen_recording_mobile.mp4"
OUTPUT_DESKTOP="static/images/screen_recording_desktop.mp4"

# Check input exists
if [ ! -f "$INPUT" ]; then
    echo "❌ Input file not found: $INPUT"
    exit 1
fi

ORIG_SIZE=$(du -h "$INPUT" | cut -f1)
echo "Original video: $ORIG_SIZE"
echo ""

# Create mobile version (720p, CRF 28)
echo "1️⃣  Creating MOBILE version (720p, ~1-2MB)..."
echo "   This may take 2-3 minutes..."
echo ""

ffmpeg -i "$INPUT" \
    -vf "scale=-2:720" \
    -c:v libx264 \
    -crf 28 \
    -preset slow \
    -profile:v main \
    -level 4.0 \
    -movflags +faststart \
    -an \
    -y "$OUTPUT_MOBILE" 2>&1 | grep -E "(Duration|frame=|time=|size=)" | tail -10

if [ $? -eq 0 ]; then
    MOBILE_SIZE=$(du -h "$OUTPUT_MOBILE" | cut -f1)
    echo ""
    echo "✓ Mobile version created: $MOBILE_SIZE"
else
    echo "❌ Failed to create mobile version"
    exit 1
fi

echo ""
echo "2️⃣  Creating DESKTOP version (1080p, ~2-4MB)..."
echo "   This may take 3-4 minutes..."
echo ""

# Create desktop version (1080p, CRF 23)
ffmpeg -i "$INPUT" \
    -vf "scale=-2:1080" \
    -c:v libx264 \
    -crf 23 \
    -preset slow \
    -profile:v high \
    -level 4.2 \
    -movflags +faststart \
    -an \
    -y "$OUTPUT_DESKTOP" 2>&1 | grep -E "(Duration|frame=|time=|size=)" | tail -10

if [ $? -eq 0 ]; then
    DESKTOP_SIZE=$(du -h "$OUTPUT_DESKTOP" | cut -f1)
    echo ""
    echo "✓ Desktop version created: $DESKTOP_SIZE"
else
    echo "❌ Failed to create desktop version"
    exit 1
fi

# Summary
echo ""
echo "=========================================="
echo "✓ OPTIMIZATION COMPLETE"
echo "=========================================="
echo ""
echo "Files created:"
echo "  Mobile:  $OUTPUT_MOBILE ($MOBILE_SIZE)"
echo "  Desktop: $OUTPUT_DESKTOP ($DESKTOP_SIZE)"
echo "  Original: $INPUT ($ORIG_SIZE - backup)"
echo ""

# Calculate average
MOBILE_BYTES=$(stat -c%s "$OUTPUT_MOBILE")
DESKTOP_BYTES=$(stat -c%s "$OUTPUT_DESKTOP")
ORIG_BYTES=$(stat -c%s "$INPUT")

AVG_BYTES=$(( (MOBILE_BYTES + DESKTOP_BYTES) / 2 ))
SAVINGS_BYTES=$(( ORIG_BYTES - AVG_BYTES ))
SAVINGS_PERCENT=$(( (SAVINGS_BYTES * 100) / ORIG_BYTES ))

echo "Bandwidth savings per page load:"
echo "  Before: $ORIG_SIZE"
echo "  After:  $(echo "scale=2; $AVG_BYTES / 1024 / 1024" | bc) MB (average)"
echo "  Saved:  $(echo "scale=2; $SAVINGS_BYTES / 1024 / 1024" | bc) MB ($SAVINGS_PERCENT% reduction)"
echo ""
echo "✅ Next steps:"
echo "  1. Test videos in browser (see COMPLETE_VIDEO_OPTIMIZATION.md)"
echo "  2. Check quality on mobile and desktop"
echo "  3. Deploy if satisfied!"
echo "  4. Original backed up at: static/images/originals/video/"
echo ""
