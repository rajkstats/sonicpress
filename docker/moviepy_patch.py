"""
Patch for MoviePy to handle ImageMagick security policy issues.
This file should be imported before using MoviePy.
"""

import os
import sys
from pathlib import Path

# Set environment variables to disable ImageMagick security
os.environ['MAGICK_CONFIGURE_PATH'] = str(Path(__file__).parent)
os.environ['MAGICK_SECURITY_POLICY'] = '1'

# Print debug info
print(f"MoviePy patch: Setting MAGICK_CONFIGURE_PATH to {os.environ['MAGICK_CONFIGURE_PATH']}")
print(f"MoviePy patch: Setting MAGICK_SECURITY_POLICY to {os.environ['MAGICK_SECURITY_POLICY']}")

# Patch MoviePy's config
try:
    from moviepy.config import IMAGEMAGICK_BINARY
    # Make sure ImageMagick is in the PATH
    if IMAGEMAGICK_BINARY == 'auto-detect':
        from moviepy.config import change_settings
        # Try to find convert binary
        import subprocess
        try:
            convert_binary = subprocess.check_output(['which', 'convert']).decode('utf-8').strip()
            change_settings({"IMAGEMAGICK_BINARY": convert_binary})
            print(f"MoviePy: Using ImageMagick binary at {convert_binary}")
        except:
            print("MoviePy: Could not auto-detect ImageMagick binary, using default")
except ImportError:
    print("MoviePy config not available, skipping patch")

# Patch PIL.Image.ANTIALIAS deprecation
try:
    from PIL import Image
    if not hasattr(Image, "ANTIALIAS"):
        try:
            # For newer PIL versions
            Image.ANTIALIAS = Image.Resampling.LANCZOS
            print("Patched PIL.Image.ANTIALIAS with Image.Resampling.LANCZOS")
        except AttributeError:
            # For very old PIL versions
            Image.ANTIALIAS = Image.LANCZOS
            print("Patched PIL.Image.ANTIALIAS with Image.LANCZOS")
except ImportError:
    print("PIL not available, skipping ANTIALIAS patch")

# We don't need to patch MoviePy's ImageClip here since agent.py has a fallback patch
# that works correctly. This avoids the "type object 'ImageClip' has no attribute 'resize'" error.
print("MoviePy patches applied successfully - resize will be patched in agent.py") 