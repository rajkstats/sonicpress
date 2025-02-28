#!/usr/bin/env python3
"""
Test script to verify the MoviePy patch is working correctly.
This script creates a simple video with text to ensure
that ImageMagick and MoviePy are working properly.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the patch
parent_dir = str(Path(__file__).parent.parent)
sys.path.append(parent_dir)

print("Testing MoviePy patch...")
print(f"Current directory: {os.getcwd()}")
print(f"Python version: {sys.version}")
print(f"Path: {sys.path}")

# First, try to import the patch
try:
    print("Importing moviepy_patch...")
    import moviepy_patch
    print("Successfully imported moviepy_patch")
except ImportError as e:
    print(f"Error importing moviepy_patch: {e}")
    print("Continuing without the patch...")

# Import PIL and check for ANTIALIAS
try:
    from PIL import Image
    print(f"PIL version: {Image.__version__}")
    print(f"PIL has ANTIALIAS: {hasattr(Image, 'ANTIALIAS')}")
    if hasattr(Image, 'ANTIALIAS'):
        print(f"ANTIALIAS value: {Image.ANTIALIAS}")
    if hasattr(Image, 'Resampling'):
        print(f"Resampling.LANCZOS value: {Image.Resampling.LANCZOS}")
except ImportError as e:
    print(f"Error importing PIL: {e}")

# Check ImageMagick configuration
print("\nChecking ImageMagick configuration:")
print(f"MAGICK_CONFIGURE_PATH: {os.environ.get('MAGICK_CONFIGURE_PATH', 'Not set')}")
print(f"MAGICK_SECURITY_POLICY: {os.environ.get('MAGICK_SECURITY_POLICY', 'Not set')}")

# Import MoviePy components
try:
    print("\nImporting MoviePy components...")
    from moviepy.editor import (
        ColorClip, TextClip, CompositeVideoClip
    )
    print("Successfully imported MoviePy components")
    
    # Create a simple test video
    print("Creating test video...")
    
    # Create a color background
    color_clip = ColorClip((640, 360), color=(0, 0, 128)).set_duration(2)
    
    # Create a text clip
    text_clip = TextClip(
        "MoviePy Test", 
        fontsize=70, 
        color="white", 
        font="Arial-Bold"
    ).set_position('center').set_duration(2)
    
    # Combine clips
    final_clip = CompositeVideoClip([color_clip, text_clip])
    
    # Write to file
    output_path = "test_moviepy_output.mp4"
    print(f"Writing test video to {output_path}...")
    final_clip.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio=False,
        threads=4,
        preset="ultrafast",
        verbose=False
    )
    
    print(f"Test video created successfully: {output_path}")
    
except ImportError as e:
    print(f"Error importing MoviePy: {e}")
except Exception as e:
    print(f"Error creating test video: {e}")
    import traceback
    traceback.print_exc()

print("\nTest completed.") 