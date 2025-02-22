import os
from dotenv import load_dotenv

load_dotenv()

# API Keys
EXA_API_KEY = os.getenv('EXA_API_KEY')
ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY')

# Cloud Storage
GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME', 'aimakers-workspace')
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# Function definitions for the agent
FUNCTION_DEFINITIONS = {
    "get_preferences": {
        "description": "Fetch user preferences from storage.",
        "params": {}
    },
    "fetch_and_summarize": {
        "description": "Fetch news articles using user preferences and generate summaries in one pass.",
        "params": {
            "preferences": "User preferences dictionary",
            "model": "Optional: LLM model to use for generation (default: mistral/mistral-small-latest)"
        }
    },
    "generate_news_script": {
        "description": "Create a natural, conversational news brief from summarized articles.",
        "params": {
            "summarized_results": "List of categories with summarized articles",
            "preferences": "User preferences dictionary",
            "model": "Optional: LLM model to use (default: mistral/mistral-small-latest)",
            "temperature": "Optional: Temperature for generation (default: 0.7)"
        }
    },
    "text_to_speech": {
        "description": "Convert news script to speech and generate audio.",
        "params": {
            "user_text": "News script to convert to audio",
            "voice_id": "Voice ID for TTS"
        }
    },
    "upload_audio": {
        "description": "Upload the audio file to Google Cloud Storage and return a GCS URL.",
        "params": {
            "audio_file_path": "Path to the MP3 file to upload"
        }
    }
} 