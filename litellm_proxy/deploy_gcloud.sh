#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}LiteLLM Proxy Direct Deployment to Google Cloud Run${NC}"
echo "This script will deploy the LiteLLM Proxy directly to Google Cloud Run"
echo

# Check if MISTRAL_API_KEY is set
if [ -z "$MISTRAL_API_KEY" ]; then
    echo -e "${RED}Error: MISTRAL_API_KEY environment variable is not set${NC}"
    echo "Please set it with: export MISTRAL_API_KEY=your_api_key_here"
    exit 1
fi

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo -e "${RED}Error: gcloud CLI is not installed${NC}"
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check if user is logged in to gcloud
if ! gcloud auth list --filter=status:ACTIVE --format="value(account)" &> /dev/null; then
    echo -e "${YELLOW}You are not logged in to gcloud. Please login:${NC}"
    gcloud auth login
fi

# Get project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo -e "${YELLOW}No project selected. Please select a project:${NC}"
    gcloud projects list
    echo
    read -p "Enter project ID: " PROJECT_ID
    gcloud config set project $PROJECT_ID
fi

echo -e "${GREEN}Using project: ${PROJECT_ID}${NC}"

# Check if Cloud Run API is enabled
if ! gcloud services list --enabled --filter="name:run.googleapis.com" | grep -q run.googleapis.com; then
    echo -e "${YELLOW}Cloud Run API is not enabled. Enabling...${NC}"
    gcloud services enable run.googleapis.com
fi

# Build the Docker image
echo -e "${GREEN}Building Docker image...${NC}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/litellm-proxy:latest"
docker build -t $IMAGE_NAME .

# Push the image to Google Container Registry
echo -e "${GREEN}Pushing image to Google Container Registry...${NC}"
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy litellm-proxy \
    --image=$IMAGE_NAME \
    --platform=managed \
    --region=us-central1 \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=1 \
    --max-instances=10 \
    --timeout=3600 \
    --set-env-vars=MISTRAL_API_KEY=$MISTRAL_API_KEY \
    --allow-unauthenticated

# Get the service URL
SERVICE_URL=$(gcloud run services describe litellm-proxy --platform managed --region us-central1 --format 'value(status.url)')

echo -e "${GREEN}LiteLLM Proxy is deployed at: ${SERVICE_URL}${NC}"
echo
echo "To use this proxy with your application, run:"
echo "export LITELLM_PROXY_URL=${SERVICE_URL}"
echo "cd .. && python litellm_proxy/update_app.py"
echo
echo "Then run your application as usual:"
echo "streamlit run streamlit_app.py" 