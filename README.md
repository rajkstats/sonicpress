# The SonicPress Times 🎙️

Your On-Demand Newsroom - Built for ElevenLabs x a16z AI Agents Hackathon 2025

##  Demo

https://github.com/rajkstats/agentic-news/assets/demo/sonicpress_news.mp4

## Features

- **Personalized News Aggregation**: Multi-category news curation with custom topic support
- **AI-Powered Summarization**: Intelligent content distillation using Mistral AI
- **Smart Relevance Filtering**: Ensures only topic-relevant articles are included in your briefing
- **Dynamic Voice Synthesis**: ElevenLabs-powered narration with 3 distinct modes:
  - 🌅 Morning Calm: Warm, relaxed delivery
  - 🌙 Evening Energetic: Dynamic, engaging style
  - ⚡ Breaking Urgent: Authoritative, urgent tone
- **Real-time Video Generation**: Automated video creation with dynamic image fetching
- **Cloud Integration**: Google Cloud Storage for asset management
- **Modern Web Interface**: Streamlit-based UI with NYTimes-inspired styling
- **Cloud-Ready**: Optimized for Google Cloud Run deployment

## 🛠️ Tech Stack

- **Core**: Python 3.11+, Poetry
- **AI/ML**: 
  - ElevenLabs API (Voice Synthesis)
  - Mistral AI (Text Processing)
  - LiteLLM for model management
- **Frontend**: Streamlit
- **Storage**: Google Cloud Storage
- **News Source**: Exa News API
- **Video Processing**: MoviePy, FFmpeg
- **Cloud Platform**: Google Cloud Run

## 📋 Prerequisites

- Python 3.11+
- Poetry for dependency management
- FFmpeg installed on system
- API Keys for:
  - ElevenLabs
  - Mistral AI
  - Exa News
- Google Cloud credentials (optional for cloud storage)

## 🚀 Quick Start

1. **Clone the Repository**:
```bash
git clone https://github.com/yourusername/agentic-news.git
cd agentic-news
```

2. **Install Dependencies**:
```bash
poetry install
```

3. **Environment Setup**:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```env
EXA_API_KEY=your_exa_key
ELEVENLABS_API_KEY=your_elevenlabs_key
MISTRAL_API_KEY=your_mistral_key
GCS_BUCKET_NAME=your_bucket_name (optional)
GOOGLE_CREDS_JSON=path_to_your_creds.json (optional)
```

4. **Run the Application**:
```bash
poetry run streamlit run streamlit_app.py
```

## ☁️ Cloud Run Deployment

### Option 1: Using the Deployment Script (Recommended)

The easiest way to deploy SonicPress to Google Cloud Run is using the provided deployment script:

```bash
# Make the script executable
chmod +x deploy_to_cloud_run.sh

# Run the deployment script
./deploy_to_cloud_run.sh
```

The script will:
1. Check for required dependencies (gcloud CLI)
2. Verify you're logged into Google Cloud
3. Create necessary API keys in Secret Manager
4. Create a GCS bucket for media storage
5. Build and push the Docker image
6. Deploy the application to Cloud Run

### Option 2: Manual Deployment

If you prefer to deploy manually, follow these steps:

1. **Set up API Keys in Secret Manager**:
```bash
# IMPORTANT: Use echo -n to avoid newline characters in your secrets
echo -n "your_exa_key" | gcloud secrets create sonicpress-exa-key --data-file=-
echo -n "your_elevenlabs_key" | gcloud secrets create sonicpress-elevenlabs-key --data-file=-
echo -n "your_mistral_key" | gcloud secrets create sonicpress-mistral-key --data-file=-
echo -n "your_bucket_name" | gcloud secrets create sonicpress-gcs-bucket --data-file=-
echo -n "your_litellm_proxy_url" | gcloud secrets create sonicpress-litellm-proxy-url --data-file=-
```

2. **Create a GCS Bucket for Media Storage**:
```bash
gsutil mb -l us-central1 gs://your_bucket_name
gsutil iam ch allUsers:objectViewer gs://your_bucket_name
```

3. **Build and Push the Docker Image**:
```bash
# Build the image
docker build -t gcr.io/your-project-id/sonicpress:latest .

# Push to Google Container Registry
docker push gcr.io/your-project-id/sonicpress:latest
```

4. **Deploy to Cloud Run**:
```bash
gcloud run deploy sonicpress \
  --image=gcr.io/your-project-id/sonicpress:latest \
  --platform=managed \
  --region=us-central1 \
  --memory=2Gi \
  --cpu=2 \
  --min-instances=0 \
  --max-instances=10 \
  --timeout=3600 \
  --set-secrets="MISTRAL_API_KEY=sonicpress-mistral-key:latest,EXA_API_KEY=sonicpress-exa-key:latest,ELEVENLABS_API_KEY=sonicpress-elevenlabs-key:latest" \
  --set-env-vars="LITELLM_PROXY_URL=your_litellm_proxy_url,GCS_BUCKET_NAME=your_bucket_name" \
  --allow-unauthenticated
```

### Troubleshooting Cloud Run Deployment

If you encounter issues with your Cloud Run deployment, check the following:

1. **API Key Format**: Ensure your API keys don't contain newline characters. Use `echo -n` when creating secrets.
   ```bash
   echo -n "your_api_key" | gcloud secrets versions add sonicpress-exa-key --data-file=-
   ```

2. **Check Logs**: View the service logs to identify specific errors.
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sonicpress" --limit=20
   ```

3. **Update Environment Variables**: If you need to update environment variables or secrets:
   ```bash
   gcloud run services update sonicpress --region=us-central1 --set-secrets=SECRET_NAME=secret-name:latest
   ```

4. **Verify Configuration**: Check the current configuration of your service:
   ```bash
   gcloud run services describe sonicpress --region=us-central1 --format="yaml(spec.template.spec.containers[0].env)"
   ```

5. **LiteLLM Proxy**: If using the LiteLLM Proxy, ensure it's properly deployed and accessible.

## 🐳 Local Docker Deployment

Build and run with Docker:

```bash
# Build the image
docker build -t sonicpress .

# Run the container
docker run -d -p 8080:8080 \
  -e EXA_API_KEY=your_key \
  -e ELEVENLABS_API_KEY=your_key \
  -e MISTRAL_API_KEY=your_key \
  -e GCS_BUCKET_NAME=your_bucket \
  -e GOOGLE_CREDS_JSON=your_creds \
  sonicpress
```

## 🎯 Usage

1. Select news categories or enter custom topics
2. Choose your preferred voice mode
3. Adjust content settings (articles per topic, news age)
4. Click "Compile My Headlines"
5. Download the generated video or audio

## 🔧 Advanced Features

### Smart Relevance Filtering

The system uses AI to ensure only topic-relevant articles are included in your briefing:

- **Contextual Understanding**: Recognizes related technologies and companies
- **Adaptive Relevance**: Considers both direct and indirect relevance to topics

### Voice Settings

Each voice mode has optimized parameters:
```python
VOICE_SETTINGS = {
    "Morning Calm": {
        "stability": 0.71,
        "similarity_boost": 0.85,
        "style": 0.35,
        "speed": 1.0
    },
    "Evening Energetic": {
        "stability": 0.71,
        "similarity_boost": 0.85,
        "style": 0.35,
        "speed": 1.0
    },
    "Breaking Urgent": {
        "stability": 0.71,
        "similarity_boost": 0.85,
        "style": 0.35,
        "speed": 1.0
    }
}
```

### Video Generation

The system automatically creates engaging news videos:

- **Dynamic Image Fetching**: Retrieves relevant images for each article
- **Structured Layout**: Organizes content with headlines, images, and summaries
- **Scrolling Ticker**: Displays headlines in a news-style ticker
- **Adaptive Formatting**: Adjusts layout based on available content
- **Resolution**: 1280x720 with H.264 encoding
- **Audio**: AAC codec, 44.1kHz

## LiteLLM Proxy Integration

SonicPress uses a LiteLLM Proxy for improved reliability and performance of LLM API calls. The proxy provides:

- **Fallbacks**: If one model fails, it automatically retries with another model
- **Load balancing**: Distributes requests across multiple models or providers
- **Unified API**: Uses the same API for all LLM providers

### Deploying the LiteLLM Proxy to Cloud Run

For optimal performance, we recommend deploying the LiteLLM Proxy to Cloud Run:

```bash
# Navigate to the litellm_proxy directory
cd litellm_proxy

# Make the deployment script executable
chmod +x deploy_gcloud.sh

# Set your Mistral API key
export MISTRAL_API_KEY=your_mistral_api_key

# Run the deployment script
./deploy_gcloud.sh
```

The script will:
1. Build a Docker image for the LiteLLM Proxy
2. Push it to Google Container Registry
3. Deploy it to Cloud Run with the appropriate configuration
4. Return the service URL to use in your application

### Using the LiteLLM Proxy Locally

If you prefer to run the LiteLLM Proxy locally for development:

```bash
# Set your Mistral API key
export MISTRAL_API_KEY=your_api_key_here

# Navigate to the litellm_proxy directory
cd litellm_proxy

# Build and run the Docker container
docker build -t litellm-proxy .
docker run -d -p 8080:8080 -e MISTRAL_API_KEY=$MISTRAL_API_KEY litellm-proxy
```

### Updating Your Application to Use the Proxy

After deploying the LiteLLM Proxy, update your application to use it:

```bash
# Set the LITELLM_PROXY_URL environment variable
export LITELLM_PROXY_URL=https://your-litellm-proxy-url

# Update the application configuration
python litellm_proxy/update_app.py
```

### Troubleshooting LiteLLM Proxy Issues

If you encounter issues with the LiteLLM Proxy:

1. **Check Proxy Logs**: View the proxy service logs to identify errors.
   ```bash
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=litellm-proxy" --limit=20
   ```

2. **Verify API Keys**: Ensure your Mistral API key is correctly set in the proxy service.
   ```bash
   echo -n "your_mistral_api_key" | gcloud secrets versions add litellm-mistral-key --data-file=-
   gcloud run services update litellm-proxy --region=us-central1 --set-env-vars=MISTRAL_API_KEY=your_mistral_api_key
   ```

3. **Test the Proxy**: Send a test request to verify it's working.
   ```bash
   curl -X POST "https://your-litellm-proxy-url/v1/chat/completions" \
     -H "Content-Type: application/json" \
     -d '{
       "model": "mistral-small",
       "messages": [{"role": "user", "content": "Hello, world!"}]
     }'
   ```

### Troubleshooting "No articles found" Issues

If you encounter "No articles found" errors, try the following solutions:

1. **Check API Keys**: Ensure your API keys are correctly formatted and don't contain newline characters.
   ```bash
   # Update the EXA_API_KEY in Secret Manager (remove any newline characters)
   echo -n "your_exa_api_key" | gcloud secrets versions add sonicpress-exa-key --data-file=-
   
   # Update the service to use the latest version
   gcloud run services update sonicpress --region=us-central1 --set-secrets=EXA_API_KEY=sonicpress-exa-key:latest
   ```

2. **Verify Environment Variables**: Make sure all required environment variables are set in your service.
   ```bash
   # Check the current configuration
   gcloud run services describe sonicpress --region=us-central1 --format="yaml(spec.template.spec.containers[0].env)"
   ```

3. **Broaden Search Parameters**: Try using more general topics or a broader date range.
   - In the UI, select broader categories like "Tech and Innovation" instead of specific technologies
   - Increase the "News age (days)" slider to search for older articles

4. **Check Logs for Specific Errors**: Look for error messages in the logs.
   ```bash
   # Check for errors related to the Exa API
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sonicpress AND textPayload:Exa" --limit=20
   
   # Check for errors related to the Mistral API
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=sonicpress AND textPayload:Mistral" --limit=20
   ```

5. **Verify LiteLLM Proxy Connection**: Ensure the LiteLLM Proxy is working correctly.
   ```bash
   # Check if the LiteLLM Proxy URL is correctly set
   gcloud run services describe sonicpress --region=us-central1 --format="value(spec.template.spec.containers[0].env[?(@.name=='LITELLM_PROXY_URL')].value)"
   
   # Check the LiteLLM Proxy logs
   gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=litellm-proxy" --limit=20
   ```

## 🔍 Troubleshooting Common Issues

### MoviePy/ImageMagick Errors

If you encounter errors like:
```
MoviePy Error: creation of None failed because of the following error:
convert-im6.q16: no images defined `PNG32:/tmp/tmpXXXXXXX.png' @ error/convert.c/ConvertImageCommand/3229.
```

This is related to ImageMagick configuration. Here's how to fix it:

1. **For Local Development**:
   - Ensure ImageMagick is installed: `apt-get install imagemagick`
   - Modify the ImageMagick policy file:
     ```bash
     sudo nano /etc/ImageMagick-6/policy.xml
     ```
   - Update resource limits and permissions:
     ```xml
     <!-- Increase memory limits -->
     <policy domain="resource" name="memory" value="8GiB"/>
     <policy domain="resource" name="map" value="4GiB"/>
     <policy domain="resource" name="disk" value="8GiB"/>
     
     <!-- Allow PDF operations if needed -->
     <policy domain="coder" rights="read|write" pattern="PDF" />
     ```

2. **For Docker/Cloud Run Deployment**:
   - The Dockerfile already includes the necessary configuration
   - If you're still encountering issues, check that the ImageMagick policy is being properly modified during the build process
   - You can verify the policy file inside the container:
     ```bash
     docker exec -it your_container_id cat /etc/ImageMagick-6/policy.xml
     ```

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request


## Hackathon Context

Built for the ElevenLabs x a16z AI Agents Hackathon 2025, focusing on:
- Voice AI Innovation
- Autonomous Agents
- Real-world Applications

##  Acknowledgments

- ElevenLabs for voice synthesis technology
- a16z for hackathon organization
- Mistral AI for language processing
- Exa for news search API
- Google Cloud Platform for infrastructure 