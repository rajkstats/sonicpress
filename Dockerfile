FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    ffmpeg \
    imagemagick \
    libxkbcommon0 \
    libxrandr2 \
    libxss1 \
    libxtst6 \
    libgl1-mesa-glx \
    libegl1-mesa \
    libopengl0 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Configure ImageMagick policy to allow all operations
RUN if [ -f /etc/ImageMagick-6/policy.xml ]; then \
        # Allow PDF operations \
        sed -i 's/rights="none" pattern="PDF"/rights="read|write" pattern="PDF"/' /etc/ImageMagick-6/policy.xml && \
        # Allow memory and disk resource limits \
        sed -i 's/domain="resource" name="memory"/domain="resource" name="memory" value="8GiB"/' /etc/ImageMagick-6/policy.xml && \
        sed -i 's/domain="resource" name="map"/domain="resource" name="map" value="4GiB"/' /etc/ImageMagick-6/policy.xml && \
        sed -i 's/domain="resource" name="disk"/domain="resource" name="disk" value="8GiB"/' /etc/ImageMagick-6/policy.xml && \
        # Allow all path operations \
        sed -i 's/<policy domain="path" rights="none" pattern="@\*"/<policy domain="path" rights="read|write" pattern="@*"/' /etc/ImageMagick-6/policy.xml; \
    fi

# Copy application code first
COPY . .

# Install poetry and dependencies
ENV PATH="/root/.local/bin:$PATH"
RUN curl -sSL https://install.python-poetry.org | python3 - \
    && poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-ansi

# Create necessary directories
RUN mkdir -p /app/output

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/google_creds.json
ENV PYTHONUNBUFFERED=1
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["sh", "-c", "echo $GOOGLE_CREDS_JSON > /app/google_creds.json && poetry run streamlit run streamlit_app.py --server.port=$PORT --server.address=$HOST"] 