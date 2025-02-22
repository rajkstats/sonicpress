import os

# API Keys
EXA_API_KEY = os.environ.get('EXA_API_KEY')
ELEVENLABS_API_KEY = os.environ.get('ELEVENLABS_API_KEY')
MISTRAL_API_KEY = os.environ.get('MISTRAL_API_KEY')

# Service URLs
ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# Storage
GCS_BUCKET_NAME = os.environ.get('GCS_BUCKET_NAME')

# Function definitions for the agent
FUNCTION_DEFINITIONS = [
    {
        "name": "get_preferences",
        "description": "Get user preferences for news categories and voice settings",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "fetch_and_summarize",
        "description": "Fetch and summarize news articles based on preferences",
        "parameters": {
            "type": "object",
            "properties": {
                "preferences": {
                    "type": "object",
                    "description": "User preferences including categories and date range"
                }
            },
            "required": ["preferences"]
        }
    },
    {
        "name": "generate_news_script",
        "description": "Generate a news script from summarized articles",
        "parameters": {
            "type": "object",
            "properties": {
                "summarized_results": {
                    "type": "array",
                    "description": "List of summarized news articles"
                },
                "preferences": {
                    "type": "object",
                    "description": "User preferences"
                }
            },
            "required": ["summarized_results", "preferences"]
        }
    },
    {
        "name": "text_to_speech",
        "description": "Convert text to speech using ElevenLabs",
        "parameters": {
            "type": "object",
            "properties": {
                "user_text": {
                    "type": "string",
                    "description": "Text to convert to speech"
                },
                "voice_id": {
                    "type": "string",
                    "description": "ElevenLabs voice ID"
                }
            },
            "required": ["user_text", "voice_id"]
        }
    },
    {
        "name": "upload_audio",
        "description": "Upload audio file to cloud storage",
        "parameters": {
            "type": "object",
            "properties": {
                "audio_file_path": {
                    "type": "string",
                    "description": "Path to the audio file"
                }
            },
            "required": ["audio_file_path"]
        }
    }
] 