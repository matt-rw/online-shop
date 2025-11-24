#!/usr/bin/env python3
"""
Create mobile-optimized video using ffmpeg-python
Keeps original video for desktop, creates smaller version for mobile
"""
import os
import subprocess
from pathlib import Path

def optimize_video_for_mobile(input_path, output_path, resolution='720', crf=28):
    """
    Create mobile-optimized MP4 video using ffmpeg.

    Args:
        input_path: Path to original video
        output_path: Path for optimized output
        resolution: Height in pixels (width auto-scaled)
        crf: Constant Rate Factor (18-28 recommended, higher=smaller file)
    """
    print(f"Optimizing video for mobile...")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    print(f"Target resolution: {resolution}p")
    print(f"Quality (CRF): {crf}")
    print("-" * 60)

    # FFmpeg command for high-quality mobile optimization
    cmd = [
        'ffmpeg',
        '-i', input_path,
        '-vf', f'scale=-2:{resolution}',  # Scale to 720p height, width auto
        '-c:v', 'libx264',                # H.264 codec
        '-crf', str(crf),                 # Quality (28 = good balance)
        '-preset', 'slow',                # Slower = better compression
        '-profile:v', 'main',             # Compatibility profile
        '-level', '4.0',                  # Compatibility level
        '-movflags', '+faststart',        # Enable streaming
        '-an',                            # Remove audio (video is muted anyway)
        '-y',                             # Overwrite output
        output_path
    ]

    try:
        # Run ffmpeg
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Get file sizes
        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        reduction = (1 - new_size / original_size) * 100

        print("\n✓ Video optimization complete!")
        print(f"  Original: {original_size / 1024 / 1024:.2f} MB")
        print(f"  Optimized: {new_size / 1024 / 1024:.2f} MB")
        print(f"  Reduction: {reduction:.1f}%")

        return True

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Error during video optimization:")
        print(f"  {e.stderr}")
        return False
    except FileNotFoundError:
        print("\n✗ ffmpeg not found!")
        print("\nPlease install ffmpeg:")
        print("  Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("  macOS: brew install ffmpeg")
        print("  Windows: Download from https://ffmpeg.org/download.html")
        return False

def main():
    # Paths
    input_video = Path('static/images/screen_recording.mov')
    output_mobile = Path('static/images/screen_recording_mobile.mp4')

    print("=" * 60)
    print("MOBILE VIDEO OPTIMIZATION")
    print("=" * 60)
    print("\nStrategy: Create optimized mobile version, keep original for desktop")
    print("")

    if not input_video.exists():
        print(f"✗ Input video not found: {input_video}")
        return

    # Create mobile version (720p, CRF 28)
    success = optimize_video_for_mobile(
        str(input_video),
        str(output_mobile),
        resolution='720',  # 720p for mobile
        crf=28             # Good quality/size balance
    )

    if success:
        print("\n" + "=" * 60)
        print("✓ OPTIMIZATION COMPLETE")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Update home_page.html to use responsive video sources")
        print("  2. Test on mobile and desktop")
        print("  3. Original video kept for desktop (best quality)")
        print("")
        print("HTML example:")
        print('  <video autoplay muted loop playsinline>')
        print('    <!-- Mobile devices get optimized version -->')
        print('    <source src="{% static \'images/screen_recording_mobile.mp4\' %}"')
        print('            type="video/mp4"')
        print('            media="(max-width: 768px)">')
        print('    <!-- Desktop/tablet gets original quality -->')
        print('    <source src="{% static \'images/screen_recording.mov\' %}"')
        print('            type="video/mp4">')
        print('  </video>')
        print("")
    else:
        print("\n✗ Optimization failed. See VIDEO_OPTIMIZATION_README.md for alternatives.")

if __name__ == '__main__':
    main()
