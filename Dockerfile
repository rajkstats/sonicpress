FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    software-properties-common \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy application code first
COPY . .

# Install poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --without dev --no-interaction --no-ansi

# Expose port
EXPOSE 8080

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/google_creds.json

# Command to run the application
CMD echo $GOOGLE_CREDS_JSON > /app/google_creds.json && poetry run streamlit run streamlit_app.py --server.port=$PORT --server.address=$HOST 