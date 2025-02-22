# SonicPress 🎙️

AI-Powered Audio News Generator with ElevenLabs Voice Technology

## Features

- 🎯 Multi-category news aggregation
- 🤖 AI-powered news summarization
- 🗣️ Advanced voice synthesis with multiple personas
- 📊 Customizable content settings
- ☁️ Cloud storage integration

## Prerequisites

- Python 3.11+
- Poetry for dependency management
- Google Cloud account (for storage)
- API keys for:
  - ElevenLabs
  - Exa
  - Mistral AI

## Setup

1. Clone the repository:
```bash
git clone https://github.com/rajkstats/sonicpress.git
cd sonicpress
```

2. Install dependencies:
```bash
poetry install
```

3. Set up environment variables:
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

4. Run the application:
```bash
poetry run streamlit run streamlit_app.py
```

## Environment Variables

Create a `.env` file with the following variables:

```env
EXA_API_KEY=your_exa_api_key
ELEVENLABS_API_KEY=your_elevenlabs_api_key
MISTRAL_API_KEY=your_mistral_api_key
GCS_BUCKET_NAME=your_gcs_bucket
GOOGLE_CREDS_JSON=your_base64_encoded_creds
```

## Docker Support

Build and run with Docker:

```bash
docker build -t sonicpress .
docker run -d -p 8080:8080 \
  -e EXA_API_KEY=your_key \
  -e ELEVENLABS_API_KEY=your_key \
  -e GCS_BUCKET_NAME=your_bucket \
  -e MISTRAL_API_KEY=your_key \
  -e GOOGLE_CREDS_JSON=your_creds \
  sonicpress
```

## Voice Modes

- **Morning Calm**: Warm, relaxed delivery
- **Evening Energetic**: Dynamic, engaging style
- **Breaking Urgent**: Authoritative, urgent tone

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - see LICENSE file for details 