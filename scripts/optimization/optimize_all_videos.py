#!/usr/bin/env python3
"""
Create optimized video versions for mobile and desktop
"""
import os
import subprocess
from pathlib import Path

def optimize_video(input_path, output_path, resolution, crf, profile='main'):
    """
    Create optimized video using ffmpeg.

    Args:
        input_path: Source video path
        output_path: Output video path
        resolution: Height in pixels (e.g., 720, 1080)
        crf: Quality level (18-28, lower=better)
        profile: H.264 profile (main, high)
    """
    print(f"\nOptimizing: {output_path.name}")
    print(f"  Resolution: {resolution}p")
    print(f"  Quality (CRF): {crf}")
    print(f"  Profile: {profile}")

    cmd = [
        'ffmpeg',
        '-i', str(input_path),
        '-vf', f'scale=-2:{resolution}',
        '-c:v', 'libx264',
        '-crf', str(crf),
        '-preset', 'slow',
        '-profile:v', profile,
        '-level', '4.2' if profile == 'high' else '4.0',
        '-movflags', '+faststart',
        '-an',
        '-y',
        str(output_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)

        original_size = os.path.getsize(input_path)
        new_size = os.path.getsize(output_path)
        reduction = (1 - new_size / original_size) * 100

        print(f"  ✓ Complete: {new_size / 1024 / 1024:.2f} MB ({reduction:.1f}% reduction)")
        return True

    except subprocess.CalledProcessError as e:
        print(f"  ✗ Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print(f"  ✗ ffmpeg not found!")
        return False

def main():
    input_video = Path('static/images/screen_recording.mov')
    output_mobile = Path('static/images/screen_recording_mobile.mp4')
    output_desktop = Path('static/images/screen_recording_desktop.mp4')

    print("=" * 60)
    print("VIDEO OPTIMIZATION - ALL DEVICES")
    print("=" * 60)

    if not input_video.exists():
        print(f"\n✗ Input video not found: {input_video}")
        print("\nPlease ensure screen_recording.mov exists in static/images/")
        return

    original_size = os.path.getsize(input_video)
    print(f"\nOriginal video: {original_size / 1024 / 1024:.2f} MB")
    print("-" * 60)

    # Create mobile version (720p, CRF 28)
    print("\n1. Creating MOBILE version (720p)...")
    mobile_success = optimize_video(
        input_video,
        output_mobile,
        resolution=720,
        crf=28,
        profile='main'
    )

    # Create desktop version (1080p, CRF 23)
    print("\n2. Creating DESKTOP version (1080p)...")
    desktop_success = optimize_video(
        input_video,
        output_desktop,
        resolution=1080,
        crf=23,
        profile='high'
    )

    # Summary
    print("\n" + "=" * 60)
    if mobile_success and desktop_success:
        print("✓ OPTIMIZATION COMPLETE")
        print("=" * 60)

        mobile_size = os.path.getsize(output_mobile)
        desktop_size = os.path.getsize(output_desktop)
        total_saved = (original_size * 2) - (mobile_size + desktop_size)

        print(f"\nFiles created:")
        print(f"  Mobile:  {output_mobile.name} ({mobile_size / 1024 / 1024:.2f} MB)")
        print(f"  Desktop: {output_desktop.name} ({desktop_size / 1024 / 1024:.2f} MB)")
        print(f"  Original: {input_video.name} ({original_size / 1024 / 1024:.2f} MB - backup)")

        print(f"\nSavings per page load:")
        avg_size = (mobile_size + desktop_size) / 2
        savings = original_size - avg_size
        print(f"  Before: {original_size / 1024 / 1024:.2f} MB")
        print(f"  After:  {avg_size / 1024 / 1024:.2f} MB (average)")
        print(f"  Saved:  {savings / 1024 / 1024:.2f} MB ({(savings / original_size) * 100:.1f}%)")

        print("\n✅ Next steps:")
        print("  1. Test videos in browser (see COMPLETE_VIDEO_OPTIMIZATION.md)")
        print("  2. Check quality on mobile and desktop")
        print("  3. Deploy if quality is good!")
        print("  4. Original kept as backup in case you need it")

    else:
        print("✗ OPTIMIZATION FAILED")
        print("=" * 60)
        print("\nffmpeg is required but not found.")
        print("\nAlternatives:")
        print("  1. Install ffmpeg:")
        print("     Ubuntu/Debian: sudo apt-get install ffmpeg")
        print("     macOS: brew install ffmpeg")
        print("\n  2. Use online tool:")
        print("     → https://cloudconvert.com/mov-to-mp4")
        print("\n  3. Use Handbrake:")
        print("     → https://handbrake.fr/")
        print("\nSee COMPLETE_VIDEO_OPTIMIZATION.md for detailed instructions.")

if __name__ == '__main__':
    main()
