import streamlit as st
import json
from agentic_news import NewsAgent
from datetime import datetime, timedelta

# Page config
st.set_page_config(
    page_title="SonicPress",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS with modern styling
st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');
        
        /* Global Styles */
        * {
            font-family: 'Open Sans', sans-serif;
        }
        
        /* Main Container */
        .main {
            padding: 2rem;
            max-width: 1200px;
            margin: 0 auto;
        }
        
        /* Header Styles */
        .header-container {
            background: linear-gradient(90deg, #1a1a1a 0%, #2d2d2d 100%);
            padding: 2rem;
            border-radius: 10px;
            margin-bottom: 2rem;
            color: white;
            text-align: center;
        }
        
        .header-title {
            font-size: 2.5rem !important;
            font-weight: 700 !important;
            margin: 0 !important;
            background: linear-gradient(120deg, #ffffff 0%, #f0f0f0 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-subtitle {
            color: #cccccc;
            font-size: 1.1rem !important;
            margin-top: 0.5rem !important;
        }
        
        /* Sidebar Styling */
        .sidebar .sidebar-content {
            background: #ffffff;
            padding: 1rem;
        }
        
        .sidebar-header {
            font-size: 1.2rem !important;
            font-weight: 600 !important;
            color: #1a1a1a !important;
            margin-bottom: 1rem !important;
        }
        
        /* Button Styling */
        .stButton>button {
            width: 100%;
            height: 3.5rem;
            background: #ff4b4b !important;
            color: white !important;
            font-size: 1.2rem !important;
            font-weight: 600 !important;
            border: none !important;
            border-radius: 8px !important;
            transition: all 0.3s ease !important;
        }
        
        .stButton>button:hover {
            background: #ff3333 !important;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(255, 75, 75, 0.2);
        }
        
        /* Tab Styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1rem;
            background-color: #f8f9fa;
            padding: 1rem;
            border-radius: 8px;
        }
        
        .stTabs [data-baseweb="tab"] {
            height: 3rem;
            background-color: transparent !important;
            border: none !important;
            color: #666666 !important;
            font-weight: 600 !important;
        }
        
        .stTabs [data-baseweb="tab"][aria-selected="true"] {
            color: #ff4b4b !important;
            border-bottom: 2px solid #ff4b4b !important;
        }
        
        /* Content Cards */
        .news-card {
            background: white;
            padding: 1.5rem;
            border-radius: 8px;
            border: 1px solid #eaeaea;
            margin-bottom: 1rem;
        }
        
        /* Audio Player Container */
        .audio-container {
            background: #f8f9fa;
            padding: 2rem;
            border-radius: 8px;
            border: 1px solid #eaeaea;
            margin-top: 1rem;
        }
        
        /* Progress Bar */
        .stProgress > div > div {
            background-color: #ff4b4b !important;
        }
        
        /* Success/Error Messages */
        .success-banner {
            padding: 0.75rem;
            background: #e8f5e9;
            border: 1px solid #81c784;
            border-radius: 6px;
            color: #2e7d32;
            margin: 1rem 0;
        }
        
        .error-banner {
            padding: 0.75rem;
            background: #ffebee;
            border: 1px solid #e57373;
            border-radius: 6px;
            color: #c62828;
            margin: 1rem 0;
        }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown("""
    <div class="header-container">
        <h1 class="header-title">SonicPress</h1>
        <p class="header-subtitle">Stay Informed with AI-Powered Audio News</p>
    </div>
""", unsafe_allow_html=True)

# Initialize the agent
@st.cache_resource
def get_agent():
    return NewsAgent()

agent = get_agent()

# Sidebar
with st.sidebar:
    st.markdown('<p class="sidebar-header">📋 Customize Your News</p>', unsafe_allow_html=True)
    
    st.markdown("#### 📰 News Categories")
    categories = st.multiselect(
        "Select your interests",
        ["Tech and Innovation", "Business", "Science", "World News", "Sports", "Entertainment"],
        default=["Tech and Innovation"],
        help="Choose multiple categories for a personalized news brief"
    )
    
    st.markdown("#### 🎤 Voice Settings")
    st.markdown("""
        <div style='background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px;'>
            <small>✨ Powered by ElevenLabs Advanced TTS</small>
        </div>
    """, unsafe_allow_html=True)
    
    # Voice Mode Selection
    voice_mode = st.radio(
        "Voice Mode",
        ["Morning Calm", "Evening Energetic", "Breaking Urgent"],
        help="Select the tone and style of the news narration"
    )
    
    # Custom Persona Name
    custom_persona = st.text_input(
        "Custom Persona Name (Optional)",
        help="Give your news anchor a unique name"
    )
    
    # Voice ID mapping based on categories and modes
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
    
    # Category-specific voice overrides
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
    
    st.markdown("#### ⚙️ Content Settings")
    col1, col2 = st.columns(2)
    with col1:
        num_results = st.slider(
            "Articles per topic",
            1, 5, 2,
            help="Number of articles per category"
        )
    with col2:
        days_ago = st.slider(
            "News age (days)",
            1, 30, 7,
            help="How recent should the news be?"
        )
    
    st.markdown("---")
    col3, col4 = st.columns(2)
    with col3:
        st.metric("Topics", len(categories))
    with col4:
        st.metric("Total Articles", len(categories) * num_results)
    
    # Ethical Usage Notice
    st.markdown("""
        <div style='background-color: #f8f9fa; padding: 10px; border-radius: 5px; margin-top: 20px;'>
            <small>🔒 <strong>Voice Ethics Notice:</strong> Our TTS technology respects voice authenticity and consent. Custom personas are for personal use only.</small>
        </div>
    """, unsafe_allow_html=True)

# Main content
if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False

st.info("🎯 Select your preferences in the sidebar and generate your personalized news update.")

if st.button("Generate Audio News", type="primary"):
    st.session_state.button_clicked = True
    try:
        progress_bar = st.progress(0)
        status = st.empty()
        
        # Step 1: Preferences
        status.markdown("🔄 Initializing your preferences...")
        
        # Get base voice settings from selected mode
        voice_settings = VOICE_SETTINGS[voice_mode].copy()
        
        # Apply category-specific overrides if applicable
        if len(categories) == 1 and categories[0] in CATEGORY_VOICE_OVERRIDES:
            voice_settings.update(CATEGORY_VOICE_OVERRIDES[categories[0]])
        
        preferences = {
            "categories": categories,
            "voice_id": voice_settings["voice_id"],
            "voice_settings": voice_settings,
            "num_results": num_results,
            "date": (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        }
        progress_bar.progress(20)
        
        # Step 2: Fetch News
        status.markdown("📡 Gathering latest news...")
        summaries = agent.fetch_and_summarize(preferences)
        if not summaries:
            st.markdown('<div class="error-banner">No news articles found. Please try different categories or date range.</div>', unsafe_allow_html=True)
            st.stop()
        progress_bar.progress(50)
        
        # Step 3: Generate Script
        status.markdown("✍️ Crafting your news brief...")
        script = agent.generate_news_script(summaries, preferences)
        progress_bar.progress(70)
        
        # Step 4: Text to Speech
        status.markdown("🎙️ Creating audio version...")
        audio_path = agent.text_to_speech(
            user_text=script,
            voice_id=voice_settings["voice_id"]
        )
        progress_bar.progress(90)
        
        # Clear progress indicators
        progress_bar.progress(100)
        status.empty()
        
        # Results tabs
        tabs = st.tabs(["📝 News Brief", "📰 Full Coverage", "🎧 Audio"])
        
        with tabs[0]:
            st.markdown('<div class="news-card">', unsafe_allow_html=True)
            st.markdown("### Today's News Brief")
            st.write(script)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with tabs[1]:
            for category in summaries:
                with st.expander(f"📰 {category['title']}"):
                    for article in category["articles"]:
                        st.markdown(f"""
                        <div class="news-card">
                            <h4>{article['title']}</h4>
                            <p>{article['summary']}</p>
                            <p><em>🔗 <a href="{article['source']}" target="_blank">Read full article</a></em></p>
                        </div>
                        """, unsafe_allow_html=True)
        
        with tabs[2]:
            st.markdown('<div class="audio-container">', unsafe_allow_html=True)
            
            # Display voice mode and persona info
            narrator_name = custom_persona if custom_persona else "Professional Anchor"
            st.markdown(f"""
                ### 🎧 Your Audio News Update
                <div style='background-color: #f0f0f0; padding: 15px; border-radius: 5px; margin-bottom: 15px;'>
                    <p><strong>Voice Mode:</strong> {voice_mode}</p>
                    <p><strong>Narrated by:</strong> {narrator_name}</p>
                    <p><small>Using ElevenLabs Advanced TTS Technology</small></p>
                </div>
            """, unsafe_allow_html=True)
            
            st.audio(audio_path, format='audio/mp3')
            
            try:
                with st.spinner("📤 Finalizing audio..."):
                    gcs_url = agent.upload_audio(audio_path)
                    if gcs_url:
                        st.markdown('<div class="success-banner">✅ Audio news brief ready for sharing!</div>', unsafe_allow_html=True)
                        st.code(gcs_url, language="text")
            except Exception as e:
                st.markdown('<div class="error-banner">⚠️ Audio generated but cloud upload unavailable</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
    except Exception as e:
        st.markdown(f'<div class="error-banner">❌ Error: {str(e)}</div>', unsafe_allow_html=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("""
    <div style='text-align: center; color: #666666; padding: 1rem;'>
        <p>Powered by SonicPress AI</p>
        <p style='font-size: 0.8rem'>© 2024 SonicPress</p>
    </div>
""", unsafe_allow_html=True) 