#!/bin/bash
set -e

# Check if Google credentials are provided as environment variable
if [ -n "$GOOGLE_CREDS_JSON_BASE64" ]; then
  echo "Decoding Google credentials from environment variable..."
  echo $GOOGLE_CREDS_JSON_BASE64 | base64 -d > /app/google_creds.json
  export GOOGLE_APPLICATION_CREDENTIALS=/app/google_creds.json
fi

# Create necessary directories
mkdir -p /app/output
mkdir -p /app/temp_images

# Set permissions
chmod -R 777 /app/output
chmod -R 777 /app/temp_images

# Configure ImageMagick
echo "Configuring ImageMagick..."
export MAGICK_CONFIGURE_PATH=/app/imagemagick
# Ensure policy file is readable
chmod 644 /app/imagemagick/policy.xml
# Disable security policies completely as a fallback
export MAGICK_SECURITY_POLICY=1

# Debug: Print ImageMagick configuration
echo "ImageMagick configuration:"
echo "- MAGICK_CONFIGURE_PATH: ${MAGICK_CONFIGURE_PATH}"
echo "- MAGICK_SECURITY_POLICY: ${MAGICK_SECURITY_POLICY}"
ls -la ${MAGICK_CONFIGURE_PATH}/policy.xml || echo "Policy file not found!"

# Debug: Check if ImageMagick is installed and working
echo "Testing ImageMagick installation..."
which convert || echo "ImageMagick convert not found in PATH"
convert -version || echo "Failed to get ImageMagick version"
convert -list policy || echo "Failed to list ImageMagick policies"

# Debug: Check if the MoviePy patch is working
echo "Testing MoviePy patch..."
if [ -f /app/docker/test_moviepy.py ]; then
  echo "Running MoviePy test script..."
  python /app/docker/test_moviepy.py
else
  echo "MoviePy test script not found at /app/docker/test_moviepy.py"
  # Create a simple test file
  echo "Creating a simple test file..."
  mkdir -p /app/docker
  cat > /app/docker/test_moviepy.py << 'EOF'
#!/usr/bin/env python3
"""Test script for MoviePy"""
import os
import sys
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Files in /app/docker: {os.listdir('/app/docker')}")
try:
    import moviepy
    print(f"MoviePy version: {moviepy.__version__}")
    from moviepy.editor import TextClip
    print("Successfully imported TextClip")
except ImportError as e:
    print(f"Error importing MoviePy: {e}")
EOF
  chmod +x /app/docker/test_moviepy.py
  python /app/docker/test_moviepy.py
fi

# Print environment info
echo "Starting SonicPress News application..."
echo "Python version: $(python --version)"
echo "Working directory: $(pwd)"
echo "Environment variables set:"
echo "- LITELLM_PROXY_URL: ${LITELLM_PROXY_URL:-Not set}"
echo "- STREAMLIT_SERVER_PORT: ${STREAMLIT_SERVER_PORT:-Not set}"
echo "- STREAMLIT_SERVER_ADDRESS: ${STREAMLIT_SERVER_ADDRESS:-Not set}"
echo "- MAGICK_CONFIGURE_PATH: ${MAGICK_CONFIGURE_PATH:-Not set}"

# Start the Streamlit application
echo "Starting Streamlit server..."
streamlit run streamlit_app.py 