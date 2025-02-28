#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}SonicPress News Deployment to Google Cloud Run${NC}"
echo "This script will deploy the SonicPress News application to Google Cloud Run"
echo

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

# Check if required APIs are enabled
for api in run.googleapis.com storage-api.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com; do
    if ! gcloud services list --enabled --filter="name:$api" | grep -q $api; then
        echo -e "${YELLOW}$api is not enabled. Enabling...${NC}"
        gcloud services enable $api
    fi
done

# Check if required secrets exist
REQUIRED_SECRETS=(
    "sonicpress-mistral-key"
    "sonicpress-exa-key"
    "sonicpress-elevenlabs-key"
    "sonicpress-gcs-bucket"
    "sonicpress-litellm-proxy-url"
)

MISSING_SECRETS=()
for secret in "${REQUIRED_SECRETS[@]}"; do
    if ! gcloud secrets describe $secret &>/dev/null; then
        MISSING_SECRETS+=($secret)
    fi
done

if [ ${#MISSING_SECRETS[@]} -gt 0 ]; then
    echo -e "${RED}Error: The following required secrets are missing:${NC}"
    for secret in "${MISSING_SECRETS[@]}"; do
        echo "  - $secret"
    done
    echo
    echo "Please create these secrets using:"
    echo "gcloud secrets create SECRET_NAME --data-file=/path/to/file"
    echo "or"
    echo "echo 'SECRET_VALUE' | gcloud secrets create SECRET_NAME --data-file=-"
    exit 1
fi

# Create GCS bucket if it doesn't exist
GCS_BUCKET_NAME=$(gcloud secrets versions access latest --secret=sonicpress-gcs-bucket)
if ! gsutil ls -b gs://$GCS_BUCKET_NAME &>/dev/null; then
    echo -e "${YELLOW}GCS bucket $GCS_BUCKET_NAME does not exist. Creating...${NC}"
    gsutil mb -l us-central1 gs://$GCS_BUCKET_NAME
    gsutil iam ch allUsers:objectViewer gs://$GCS_BUCKET_NAME
fi

echo -e "${GREEN}Using GCS bucket: ${GCS_BUCKET_NAME}${NC}"

# Get LiteLLM Proxy URL
LITELLM_PROXY_URL=$(gcloud secrets versions access latest --secret=sonicpress-litellm-proxy-url)
echo -e "${GREEN}Using LiteLLM Proxy URL: ${LITELLM_PROXY_URL}${NC}"

# Build the Docker image
echo -e "${GREEN}Building Docker image...${NC}"
IMAGE_NAME="gcr.io/${PROJECT_ID}/sonicpress:latest"
docker build -t $IMAGE_NAME .

# Push the image to Google Container Registry
echo -e "${GREEN}Pushing image to Google Container Registry...${NC}"
docker push $IMAGE_NAME

# Deploy to Cloud Run
echo -e "${GREEN}Deploying to Cloud Run...${NC}"
gcloud run deploy sonicpress \
    --image=$IMAGE_NAME \
    --platform=managed \
    --region=us-central1 \
    --memory=2Gi \
    --cpu=2 \
    --min-instances=0 \
    --max-instances=10 \
    --timeout=3600 \
    --set-secrets="MISTRAL_API_KEY=sonicpress-mistral-key:latest,EXA_API_KEY=sonicpress-exa-key:latest,ELEVENLABS_API_KEY=sonicpress-elevenlabs-key:latest" \
    --set-env-vars="LITELLM_PROXY_URL=${LITELLM_PROXY_URL},GCS_BUCKET_NAME=${GCS_BUCKET_NAME}" \
    --allow-unauthenticated

# Get the service URL
SERVICE_URL=$(gcloud run services describe sonicpress --platform managed --region us-central1 --format 'value(status.url)')

echo -e "${GREEN}SonicPress News is deployed at: ${SERVICE_URL}${NC}"
echo
echo "You can access your application at: ${SERVICE_URL}"
echo
echo "To update the environment variables in the future, use:"
echo "gcloud run services update sonicpress --set-env-vars=KEY=VALUE"
echo "To update the secrets in the future, use:"
echo "gcloud run services update sonicpress --set-secrets=KEY=SECRET_NAME:latest" 