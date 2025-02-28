FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir 'litellm[proxy]==1.61.13' python-dotenv gunicorn

# Copy configuration
COPY litellm_config.yaml /app/litellm_config.yaml

# Set environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

# Expose port
EXPOSE 8080

# Run the proxy with gunicorn for better performance in production
CMD exec gunicorn --bind :$PORT --workers 1 --timeout 0 --worker-class uvicorn.workers.UvicornWorker "litellm.proxy.proxy_server:app"
