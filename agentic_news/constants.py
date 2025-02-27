# Loading animation assets
LOADING_ICONS = ["⚙️", "📡", "✍️", "🎙️", "🎬"]

LOADING_QUOTES = [
    "Initializing your preferences...",
    "Gathering latest news from trusted sources...", 
    "Crafting your personalized news brief...",
    "Creating natural voice narration...",
    "Creating your news video..."
]

LOADING_POWERS = [
    "Powered by ElevenLabs & Mistral AI",
    "Powered by Exa News API", 
    "Powered by Mistral AI",
    "Powered by ElevenLabs Advanced TTS",
    "SonicPress AI"
]

FUN_FACTS = [
    "AI can process millions of news articles in seconds!",
    "AI can understand and translate news in over 100 languages.",
    "Neural networks can identify key topics across multiple sources.",
    "The world's first TV news broadcast was in 1941 by WNBT.",
    "The first news broadcast was in 1920 by 8MK in Detroit."
]

# Voice settings
VOICE_SETTINGS = {
    "Morning Calm": {
        "voice_id": "ThT5KcBeYPX3keUQqHPh",  # Rachel - warm, calm voice
        "stability": 0.85,
        "similarity_boost": 0.75,
        "style": 0.3,
        "speed": 0.8
    },
    "Evening Energetic": {
        "voice_id": "VR6AewLTigWG4xSOukaG",  # Adam - energetic, engaging voice
        "stability": 0.7,
        "similarity_boost": 0.8,
        "style": 0.6,
        "speed": 1.1
    },
    "Breaking Urgent": {
        "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni - authoritative, urgent voice
        "stability": 0.6,
        "similarity_boost": 0.9,
        "style": 0.8,
        "speed": 1.15
    }
}

CATEGORY_VOICE_OVERRIDES = {
    "Business": {
        "stability": 0.9,
        "similarity_boost": 0.7,
        "style": 0.2,  # More formal tone
        "speed": 0.95
    },
    "Sports": {
        "stability": 0.6,
        "similarity_boost": 0.85,
        "style": 0.7,  # More energetic
        "speed": 1.1
    },
    "Entertainment": {
        "stability": 0.7,
        "similarity_boost": 0.8,
        "style": 0.6,  # More casual
        "speed": 1.05
    }
} 