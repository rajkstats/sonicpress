import streamlit as st
import json
from datetime import datetime, timedelta
import requests
import re
from io import BytesIO
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

# Force reload of environment variables before importing the agent
load_dotenv(override=True)

# Import NewsAgent
from agentic_news.agent import NewsAgent

# Example constants used in a loading UI
LOADING_ICONS = ["⏳","🔄","🌐","⚙️","✅"]
LOADING_QUOTES = [
    "Gathering fresh headlines...",
    "Summarizing top stories...",
    "Generating your script...",
    "Converting text to speech...",
    "Finishing up your video..."
]
LOADING_POWERS = ["Search", "Summarize", "Script", "TTS", "Video"]
FUN_FACTS = [
    "AI can help you find stories you might miss otherwise.",
    "ElevenLabs TTS can mimic multiple voice styles.",
    "Exa indexes millions of pages for near real-time search.",
    "MoviePy compiles everything into a final video.",
    "SonicPress aims to streamline your daily news!"
]

st.set_page_config(
    page_title="SonicPress",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Add a button to clear the cache and reload credentials
if st.sidebar.button("Reload Credentials"):
    st.cache_resource.clear()
    st.sidebar.success("Credentials reloaded from .env file!")
    st.experimental_rerun()

@st.cache_resource
def get_agent():
    # This will create a new agent with fresh credentials from .env
    print("Creating new NewsAgent instance with latest credentials")
    return NewsAgent()

agent = get_agent()

# SIDEBAR
with st.sidebar:
    st.markdown("## 📰 News Categories")

    use_custom_query = st.checkbox("Add custom topic", help="Search for a custom topic")
    if use_custom_query:
        custom_query = st.text_input(
            "Enter topic",
            placeholder="e.g. Artificial Intelligence, Climate Change"
        )
        possible_categories = [
            "Tech and Innovation", "Business and Finance", "Science and Space",
            "World News", "Sports", "Entertainment", "Health and Medicine",
            "Climate and Environment", "Politics", "Education",
            "Artificial Intelligence", "Cryptocurrency", "Gaming", "Travel",
            "Food and Culture", "Automotive", "Real Estate",
            "Music", "Fashion", "Startups"
        ]
        categories = st.multiselect(
            "Additional categories (optional)",
            possible_categories,
            default=[]
        )
        if custom_query:
            categories = [custom_query] + categories
        elif not categories:
            st.warning("Please enter a topic or select categories.")
    else:
        possible_categories = [
            "Tech and Innovation", "Business and Finance", "Science and Space",
            "World News", "Sports", "Entertainment", "Health and Medicine",
            "Climate and Environment", "Politics", "Education",
            "Artificial Intelligence", "Cryptocurrency", "Gaming", "Travel",
            "Food and Culture", "Automotive", "Real Estate",
            "Music", "Fashion", "Startups"
        ]
        categories = st.multiselect(
            "Select your interests",
            possible_categories,
            default=["Tech and Innovation"]
        )

    st.markdown("### 🎤 Voice Settings")
    voice_mode = st.radio(
        "Voice Mode",
        ["Morning Calm", "Evening Energetic", "Breaking Urgent"],
        help="Select the tone and style"
    )

    st.markdown("### ⚙️ Content Settings")
    num_results = st.slider("Articles per topic", 1, 5, 2)
    days_ago = st.slider("News age (days)", 1, 30, 7)
    
    # Added image quality settings
    st.markdown("### 🖼️ Image Settings")
    min_image_width = st.slider("Min image width", 200, 800, 300)
    min_image_height = st.slider("Min image height", 200, 800, 200)
    use_placeholder = st.checkbox("Use placeholder for missing images", value=True)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Topics", len(categories))
    with col2:
        st.metric("Total Articles", len(categories) * num_results)

# Session state
if "button_clicked" not in st.session_state:
    st.session_state.button_clicked = False
if "script" not in st.session_state:
    st.session_state.script = None
if "summaries" not in st.session_state:
    st.session_state.summaries = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "video_path" not in st.session_state:
    st.session_state.video_path = None

st.title("SonicPress AI - On-Demand Audio News")

if not st.session_state.button_clicked:
    # Show an intro or placeholder
    st.info("Customize your news in the sidebar, then click below to generate.")
    if st.button("Generate News"):
        st.session_state.button_clicked = True
        st.rerun()
else:
    # Main pipeline steps
    progress_bar = st.progress(0)
    status_placeholder = st.empty()
    video_placeholder = st.empty()

    try:
        # Step 1: Build preferences
        status_placeholder.markdown("### 1) Gathering Preferences...")
        # Voice IDs mapped to your ElevenLabs voices
        voice_id_map = {
            "Morning Calm": "ThT5KcBeYPX3keUQqHPh",  # e.g. "Rachel"
            "Evening Energetic": "VR6AewLTigWG4xSOukaG",  # e.g. "Adam"
            "Breaking Urgent": "ErXwobaYiN019PkySvjV"    # e.g. "Antoni"
        }
        preferences = {
            "categories": categories,
            "voice_id": voice_id_map[voice_mode],
            "num_results": num_results,
            "date": (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
            "min_image_width": min_image_width,
            "min_image_height": min_image_height,
            "use_placeholder": use_placeholder
        }
        progress_bar.progress(20)

        # Step 2: Fetch & Summarize
        status_placeholder.markdown("### 2) Fetching and Summarizing...")
        summaries = agent.fetch_and_summarize(preferences)
        agent.state['summaries'] = summaries  # store so generate_video can use
        if not summaries:
            st.warning("No articles found. Try a broader date range or different topics.")
            st.stop()
        st.session_state.summaries = summaries
        progress_bar.progress(40)

        # Step 3: Generate Script
        status_placeholder.markdown("### 3) Generating News Script...")
        script = agent.generate_news_script(summaries, preferences)
        st.session_state.script = script
        progress_bar.progress(60)

        # Step 4: Text to Speech
        status_placeholder.markdown("### 4) Converting to Speech...")
        audio_path = agent.text_to_speech(script, voice_id=voice_id_map[voice_mode])
        st.session_state.audio_path = audio_path
        progress_bar.progress(80)

        # Step 5: Generate Video
        status_placeholder.markdown("### 5) Composing Final Video...")
        # Ensure output directory exists
        os.makedirs("output", exist_ok=True)
        video_path = agent.generate_video(script, audio_path)
        st.session_state.video_path = video_path
        progress_bar.progress(100)

        status_placeholder.empty()
        st.success("✅ Your news video is ready!")

        # Check if we got a video or just audio
        is_video = video_path.endswith(('.mp4', '.avi', '.mov', '.mkv'))
        
        if is_video:
            video_placeholder.video(video_path)
        else:
            st.audio(audio_path)
            st.warning("Video generation encountered issues. Falling back to audio-only mode.")

        with st.expander("Download Options"):
            if is_video:
                file_format = st.radio("Format", ["Video (MP4)", "Audio (MP3)"], horizontal=True)
                if file_format == "Video (MP4)":
                    st.download_button(
                        "Download Video",
                        data=open(video_path, "rb"),
                        file_name="sonicpress_news.mp4",
                        mime="video/mp4"
                    )
                else:
                    st.download_button(
                        "Download Audio",
                        data=open(audio_path, "rb"),
                        file_name="sonicpress_news.mp3",
                        mime="audio/mp3"
                    )
            else:
                st.download_button(
                    "Download Audio",
                    data=open(audio_path, "rb"),
                    file_name="sonicpress_news.mp3",
                    mime="audio/mp3"
                )

    except Exception as e:
        st.error(f"An error occurred: {e}")
        progress_bar.empty()
        status_placeholder.empty()
