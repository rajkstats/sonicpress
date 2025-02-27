# SonicPress AI 🎙️

Your On-Demand Audio Newsroom - Built for ElevenLabs x a16z AI Agents Hackathon 2024

## 🎥 Demo

https://github.com/rajkstats/agentic-news/assets/demo/sonicpress_news.mp4

## 🌟 Features

- **Personalized News Aggregation**: Multi-category news curation with custom topic support
- **AI-Powered Summarization**: Intelligent content distillation using Mistral AI
- **Dynamic Voice Synthesis**: ElevenLabs-powered narration with 3 distinct modes:
  - 🌅 Morning Calm: Warm, relaxed delivery
  - 🌙 Evening Energetic: Dynamic, engaging style
  - ⚡ Breaking Urgent: Authoritative, urgent tone
- **Real-time Video Generation**: Automated video creation with fal.ai backgrounds
- **Cloud Integration**: Google Cloud Storage for asset management
- **Modern Web Interface**: Streamlit-based UI with real-time updates
- **Cloud-Ready**: Optimized for Google Cloud Run deployment

## 🛠️ Tech Stack

- **Core**: Python 3.11+, Poetry
- **AI/ML**: 
  - ElevenLabs API (Voice Synthesis)
  - Mistral AI (Text Processing)
  - fal.ai (Image Generation)
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
  - fal.ai
  - Exa News
- Google Cloud credentials

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
FAL_KEY=your_fal_key
GCS_BUCKET_NAME=your_bucket_name
GOOGLE_CREDS_JSON=path_to_your_creds.json
```

4. **Run the Application**:
```bash
poetry run streamlit run streamlit_app.py
```

## ☁️ Cloud Run Deployment

1. **Encode Google Cloud Credentials**:
```bash
base64 path/to/your/credentials.json > creds_base64.txt
```

2. **Set up Cloud Build Secrets**:
```bash
# Create secrets for API keys
gcloud secrets create sonicpress-exa-key --data-file=<(echo $EXA_API_KEY)
gcloud secrets create sonicpress-elevenlabs-key --data-file=<(echo $ELEVENLABS_API_KEY)
gcloud secrets create sonicpress-mistral-key --data-file=<(echo $MISTRAL_API_KEY)
gcloud secrets create sonicpress-fal-key --data-file=<(echo $FAL_KEY)
gcloud secrets create sonicpress-gcs-bucket --data-file=<(echo $GCS_BUCKET_NAME)
gcloud secrets create sonicpress-google-creds --data-file=creds_base64.txt
```

3. **Deploy to Cloud Run**:
```bash
gcloud builds submit
```

The application will be deployed with:
- 2GB memory allocation
- 2 CPU cores
- 1-hour timeout for long-running operations
- Automatic scaling
- HTTPS endpoint

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
  -e FAL_KEY=your_key \
  -e GCS_BUCKET_NAME=your_bucket \
  -e GOOGLE_CREDS_JSON=your_creds \
  sonicpress
```

## 🎯 Usage

1. Select news categories or enter custom topics
2. Choose your preferred voice mode
3. Adjust content settings (articles per topic, news age)
4. Click "Produce My SonicPress Brief"
5. Download the generated video or audio

## 🔧 Configuration

### Voice Settings

Each voice mode has optimized parameters:
```python
VOICE_SETTINGS = {
    "Morning Calm": {
        "stability": 0.85,
        "similarity_boost": 0.75,
        "style": 0.3,
        "speed": 0.8
    },
    "Evening Energetic": {
        "stability": 0.7,
        "similarity_boost": 0.8,
        "style": 0.6,
        "speed": 1.1
    },
    "Breaking Urgent": {
        "stability": 0.6,
        "similarity_boost": 0.9,
        "style": 0.8,
        "speed": 1.15
    }
}
```

### Video Generation Settings

Optimized video settings for cloud deployment:
- Resolution: 1280x720
- Font sizes: Optimized for readability
- Background: AI-generated studio scenes
- Format: MP4 with H.264 encoding
- Audio: AAC codec, 44.1kHz

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🏆 Hackathon Context

Built for the ElevenLabs x a16z AI Agents Hackathon 2024, focusing on:
- Voice AI Innovation
- Autonomous Agents
- Real-world Applications

## 🙏 Acknowledgments

- ElevenLabs for voice synthesis technology
- a16z for hackathon organization
- Mistral AI for language processing
- fal.ai for image generation
- Google Cloud Platform for infrastructure 