FROM python:3.11-slim

WORKDIR /app

# Install system dependencies - only keep essential ones
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    ffmpeg \
    imagemagick \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Create a completely new ImageMagick policy file with permissive settings
COPY docker/imagemagick-policy.xml /etc/ImageMagick-6/policy.xml

# Create necessary directories first
RUN mkdir -p /app/output /app/temp_images && \
    chmod -R 777 /app/output /app/temp_images

# Copy requirements first to leverage Docker cache
COPY pyproject.toml poetry.lock ./

# Copy the agentic_news directory first to ensure it exists
COPY agentic_news ./agentic_news/

# Ensure __init__.py exists in the agentic_news directory
RUN touch ./agentic_news/__init__.py && \
    echo "# Import NewsAgent class" > ./agentic_news/__init__.py && \
    echo "from .agent import NewsAgent" >> ./agentic_news/__init__.py

# Install poetry and dependencies
ENV PATH="/root/.local/bin:$PATH"
RUN pip install --no-cache-dir --upgrade pip && \
    curl -sSL https://install.python-poetry.org | python3 - && \
    poetry config virtualenvs.create false && \
    poetry install --without dev --no-interaction --no-ansi

# Copy the rest of the application code
COPY . .

# Ensure the docker directory exists and has the MoviePy patch
RUN mkdir -p /app/docker && \
    ls -la /app/docker || echo "Docker directory is empty"

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
# Set environment variable to disable ImageMagick security
ENV MAGICK_CONFIGURE_PATH=/app/imagemagick

# Create custom ImageMagick config directory and policy
RUN mkdir -p /app/imagemagick
COPY docker/imagemagick-policy.xml /app/imagemagick/policy.xml

# Make startup script executable
RUN chmod +x /app/startup.sh

# Debug: Print directory structure
RUN echo "Directory structure:" && \
    find /app -type f -name "*.py" | sort

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["/app/startup.sh"] 