import streamlit as st
import time
import random
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta
from dotenv import load_dotenv
import webbrowser
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.http import MediaFileUpload
import requests

# Load .env variables (for agent credentials)
load_dotenv(override=True)

# Import your NewsAgent (ensure agentic_news is installed or adjust as needed)
from agentic_news.agent import NewsAgent

# Add API connectivity testing functions
def test_mistral_connectivity():
    """Test connectivity to the Mistral API."""
    api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    if not api_key:
        return False, "MISTRAL_API_KEY environment variable not set"
    
    url = "https://api.mistral.ai/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return True, "Connected successfully"
        else:
            return False, f"API returned status code {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return False, f"Error connecting to Mistral API: {str(e)}"

def test_exa_connectivity():
    """Test connectivity to the Exa API."""
    api_key = os.environ.get("EXA_API_KEY", "").strip()
    if not api_key:
        return False, "EXA_API_KEY environment variable not set"
    
    url = "https://api.exa.ai/search"
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    data = {
        "query": "test query",
        "numResults": 1
    }
    
    try:
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            return True, "Connected successfully"
        else:
            return False, f"API returned status code {response.status_code}: {response.text[:100]}"
    except Exception as e:
        return False, f"Error connecting to Exa API: {str(e)}"

# Function to check all required APIs
def check_api_connectivity():
    mistral_success, mistral_message = test_mistral_connectivity()
    exa_success, exa_message = test_exa_connectivity()
    
    return {
        "mistral": {"success": mistral_success, "message": mistral_message},
        "exa": {"success": exa_success, "message": exa_message},
        "all_success": mistral_success and exa_success
    }

################################################################################
# PAGE CONFIG AND NYTIMES-STYLE CSS
################################################################################

st.set_page_config(
    page_title="The SonicPress Times",
    page_icon="📰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# NYTimes-inspired styling
st.markdown("""
<style>
:root {
    --nyt-black: #121212;
    --nyt-dark-gray: #333333;
    --nyt-medium-gray: #666666;
    --nyt-light-gray: #f7f7f7;
    --nyt-red: #d0021b;
    --nyt-border: #e2e2e2;
}

/* Main container with a classic serif look */
.main .block-container {
    max-width: 1100px;
    margin: auto;
    padding-top: 1.5rem;
    font-family: georgia, "times new roman", times, serif;
    color: var(--nyt-black);
}

/* Sidebar styling */
[data-testid="stSidebar"] {
    background-color: var(--nyt-light-gray);
    border-right: 1px solid var(--nyt-border);
    padding-top: 1rem;
    font-family: georgia, "times new roman", times, serif;
}

/* Sidebar masthead styling to match main masthead */
.sidebar-masthead {
    text-align: center;
    border-bottom: 1px solid var(--nyt-black);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
}
.sidebar-masthead-title {
    font-family: "old english text mt", "times new roman", serif;
    font-size: 1.8rem;
    margin-bottom: 0.2rem;
    letter-spacing: -0.5px;
    color: var(--nyt-black);
    line-height: 1.1;
}
.sidebar-masthead-subtitle {
    font-family: "nyt-franklin", arial, helvetica, sans-serif;
    font-style: italic;
    font-size: 0.7rem;
    color: var(--nyt-medium-gray);
}

/* Headings with Cheltenham-like styling */
h1, h2, h3 {
    font-family: "nyt-cheltenham", georgia, "times new roman", times, serif;
    margin-bottom: 1rem;
    color: var(--nyt-black);
}

/* Masthead design */
.masthead {
    text-align: center;
    border-bottom: 2px solid var(--nyt-black);
    margin-bottom: 1.5rem;
    padding-bottom: 1rem;
}
.masthead-title {
    font-family: "old english text mt", "times new roman", serif;
    font-size: 3rem;
    margin-bottom: 0.5rem;
    letter-spacing: -1px;
    color: var(--nyt-black);
}
.masthead-date {
    font-family: "nyt-franklin", arial, helvetica, sans-serif;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 0.8rem;
    color: var(--nyt-medium-gray);
}

/* Large red button with slight hover effect */
.stButton > button {
    background-color: var(--nyt-red) !important;
    color: white !important;
    font-family: georgia, "times new roman", times, serif !important;
    font-weight: bold !important;
    border-radius: 0px !important;
    padding: 1.5rem 2rem !important;
    margin: 1rem 0 !important;
    transition: all 0.3s ease !important;
    border: none !important;
    font-size: 1.5rem !important;
    letter-spacing: 0.5px !important;
    display: block !important;
    visibility: visible !important;
    opacity: 1 !important;
}
.stButton > button:hover {
    background-color: #a00015 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 12px rgba(0,0,0,0.3) !important;
}

/* Category tags */
.category-tag {
    display: inline-block;
    background-color: var(--nyt-light-gray);
    color: var(--nyt-dark-gray);
    padding: 3px 8px;
    margin: 3px;
    font-size: 0.8em;
    font-family: "nyt-franklin", arial, helvetica, sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border: 1px solid var(--nyt-border);
}
.category-tag:hover {
    background-color: var(--nyt-border);
}

/* Summaries displayed as news cards */
.news-card {
    background-color: white;
    padding: 20px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--nyt-border);
    transition: background-color 0.2s ease;
    display: flex;
    flex-direction: column;
}
.news-card:hover {
    background-color: var(--nyt-light-gray);
}
.news-card h4 {
    font-family: "nyt-cheltenham", georgia, "times new roman", times, serif;
    font-weight: bold;
    font-size: 1.3rem;
    margin-bottom: 0.8rem;
    line-height: 1.3;
}
.news-card p {
    font-size: 1.05rem;
    line-height: 1.6;
    color: var(--nyt-dark-gray);
    margin-bottom: 1rem;
}

/* Source link */
.source-link {
    display: inline-block;
    font-family: "nyt-franklin", arial, helvetica, sans-serif;
    font-size: 0.85em;
    color: var(--nyt-dark-gray);
    text-decoration: none;
    margin-top: 5px;
    border-bottom: 1px dotted var(--nyt-dark-gray);
    align-self: flex-end;
}
.source-link:hover {
    text-decoration: underline;
    color: var(--nyt-red);
}

/* Voice option styling */
.voice-option {
    padding: 8px 0;
    margin-bottom: 10px;
    border-bottom: 1px solid var(--nyt-border);
    font-family: georgia, "times new roman", times, serif;
}
.voice-option.selected {
    border-left: 3px solid var(--nyt-black);
    padding-left: 7px;
}

/* Final video or audio block */
.media-block {
    border: 1px solid var(--nyt-border);
    margin: 20px 0;
    padding: 20px;
    background-color: var(--nyt-light-gray);
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

/* Download section */
.download-section {
    background-color: var(--nyt-light-gray);
    padding: 25px;
    margin: 30px 0;
    border: 1px solid var(--nyt-border);
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}

/* "Note from the Editor" (fun fact) */
.editor-note {
    margin-top: 30px;
    margin-bottom: 30px;
    padding: 20px;
    border-top: 1px solid var(--nyt-border);
    border-bottom: 1px solid var(--nyt-border);
    font-family: georgia, "times new roman", times, serif;
    font-size: 1rem;
    color: var(--nyt-medium-gray);
    background-color: var(--nyt-light-gray);
    font-style: italic;
}

/* Streamlit status messages (info, warning, error) */
[data-testid="stAlert"] {
    background-color: var(--nyt-light-gray);
    border: 1px solid var(--nyt-border);
    border-radius: 0;
    color: var(--nyt-dark-gray);
    font-family: georgia, "times new roman", times, serif;
}

/* Progress bar color */
.stProgress > div > div > div {
    background-color: var(--nyt-black);
}

/* Enhanced download buttons */
[data-testid="stDownloadButton"] button {
    background-color: var(--nyt-black) !important;
    color: white !important;
    text-transform: uppercase !important;
    letter-spacing: 1px !important;
    font-family: "nyt-franklin", arial, helvetica, sans-serif !important;
    font-size: 0.9rem !important;
    padding: 0.8rem 1.2rem !important;
    border-radius: 0 !important;
    transition: all 0.2s ease !important;
}
[data-testid="stDownloadButton"] button:hover {
    background-color: var(--nyt-red) !important;
    transform: translateY(-1px) !important;
}

/* Headlines section styling */
.headlines-section {
    margin-top: 40px;
    border-top: 2px solid var(--nyt-black);
    padding-top: 20px;
}

/* Fix for video player */
.stVideo video {
    width: 100%;
    max-height: 500px;
    margin: 0 auto;
    display: block;
}

/* Auto-scroll to video when ready */
.video-ready {
    scroll-margin-top: 80px;
}

/* Fix for selected topics display */
.selected-topics {
    margin-bottom: 20px;
    padding-bottom: 10px;
    border-bottom: 1px solid var(--nyt-border);
}

/* Clean section dividers */
.section-divider {
    height: 2px;
    background-color: var(--nyt-black);
    margin: 30px 0;
    width: 100%;
}

/* Consistent heading styles */
.nyt-heading {
    font-family: "nyt-cheltenham", georgia, "times new roman", times, serif;
    font-weight: bold;
    border-bottom: 1px solid var(--nyt-border);
    padding-bottom: 10px;
    margin-bottom: 20px;
    margin-top: 30px;
}

/* Fix for download section */
.download-title {
    font-family: "nyt-cheltenham", georgia, "times new roman", times, serif;
    text-transform: uppercase;
    letter-spacing: 1px;
    text-align: center;
    margin-bottom: 20px;
    font-size: 1.5rem;
}

/* Fix for columns */
[data-testid="column"] {
    padding: 0 10px;
}

/* Fix for status messages during processing */
.status-message {
    font-family: georgia, "times new roman", times, serif;
    padding: 15px;
    background-color: var(--nyt-light-gray);
    border: 1px solid var(--nyt-border);
    margin: 10px 0;
}
</style>
""", unsafe_allow_html=True)

################################################################################
# SETUP AGENT AND CACHED RESOURCES
################################################################################

@st.cache_resource
def get_agent():
    """Returns a cached instance of the NewsAgent using credentials from .env."""
    return NewsAgent()

agent = get_agent()

################################################################################
# GLOBALS
################################################################################

DEFAULT_CATEGORIES = [
            "Tech and Innovation", "Business and Finance", "Science and Space",
            "World News", "Sports", "Entertainment", "Health and Medicine",
            "Climate and Environment", "Politics", "Education",
    "Artificial Intelligence", "Cryptocurrency", "Gaming"
]

VOICE_OPTIONS = {
    "Morning Calm": {
        "id": "ThT5KcBeYPX3keUQqHPh",
        "icon": "☀️",
        "desc": "Smooth and relaxed tone, perfect for morning updates",
    },
    "Evening Energetic": {
        "id": "VR6AewLTigWG4xSOukaG",
        "icon": "🌆",
        "desc": "Upbeat and engaging, ideal for evening recaps",
    },
    "Breaking Urgent": {
        "id": "ErXwobaYiN019PkySvjV",
        "icon": "🚨",
        "desc": "Authoritative and direct, for important news",
    },
}

FUN_FACTS = [
    "MoviePy can combine images, text, and audio to produce dynamic videos.",
    "Voice technology keeps you informed even when you're on the move.",
    "AI reduces information overload by focusing on topics you truly care about.",
    "ElevenLabs can create natural-sounding speech in multiple languages.",
    "Personalized news helps you discover stories you might otherwise miss.",
    "Exa can search millions of pages in seconds for the latest headlines.",
]

# Session variables to hold state
if "fetched_summaries" not in st.session_state:
    st.session_state.fetched_summaries = None
if "news_script" not in st.session_state:
    st.session_state.news_script = None
if "audio_path" not in st.session_state:
    st.session_state.audio_path = None
if "video_path" not in st.session_state:
    st.session_state.video_path = None

################################################################################
# SIDEBAR: USER PREFERENCES + CALL TO ACTION
################################################################################

# Update sidebar header to match main masthead styling
st.sidebar.markdown("""
<div class="sidebar-masthead">
    <div class="sidebar-masthead-title">The SonicPress Times</div>
    <div class="sidebar-masthead-subtitle">Digital Edition</div>
</div>
""", unsafe_allow_html=True)

# Main call-to-action button in sidebar - moved to top for visibility
compile_button = st.sidebar.button("📜 Compile My Headlines", use_container_width=True)

st.sidebar.subheader("Sections")
use_custom_topic = st.sidebar.checkbox("Custom Topic?", value=False)

if use_custom_topic:
    custom_query = st.sidebar.text_input("Enter Topic", placeholder="e.g. Artificial Intelligence")
    additional_cats = st.sidebar.multiselect("Additional Topics", DEFAULT_CATEGORIES, default=[])
    categories = [custom_query] + additional_cats if custom_query else additional_cats
else:
    categories = st.sidebar.multiselect("Select Interests", DEFAULT_CATEGORIES, default=["Tech and Innovation"])

st.sidebar.markdown("---")
st.sidebar.subheader("Narration Voice")
voice_choice = st.sidebar.radio(
    "Choose a style:",
    list(VOICE_OPTIONS.keys()),
    format_func=lambda x: f"{VOICE_OPTIONS[x]['icon']} {x}"
)
# Display a short description below the radio
st.sidebar.markdown(f"""
<div class="voice-option selected">
  <strong>{VOICE_OPTIONS[voice_choice]['icon']} {voice_choice}</strong><br>
  <small>{VOICE_OPTIONS[voice_choice]['desc']}</small>
</div>
""", unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.subheader("Content Settings")
num_results = st.sidebar.slider("Articles per Topic", 1, 5, 3)
days_ago = st.sidebar.slider("News age (days)", 1, 30, 7)

################################################################################
# MAIN CONTENT
################################################################################

# ALWAYS display the masthead at the very top
st.markdown(f"""
<div class="masthead">
    <div class="masthead-title">The SonicPress Times</div>
    <div class="masthead-date">{datetime.now().strftime("%A, %B %d, %Y").upper()}</div>
</div>
<div style="height: 1px; background-color: #e2e2e2; margin-bottom: 10px;"></div>
""", unsafe_allow_html=True)

# Show chosen topics right after masthead
if categories:
    st.markdown('<div class="selected-topics" style="margin-bottom: 10px;">', unsafe_allow_html=True)
    st.markdown('<span style="font-family: \'nyt-franklin\', arial; text-transform: uppercase; font-size: 0.85rem; color: #666;">YOUR SELECTED TOPICS</span>', unsafe_allow_html=True)
    cat_tags = "".join(f'<span class="category-tag">{cat}</span>' for cat in categories)
    st.markdown(f"{cat_tags}", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# Single headline for "Today's Personalized Briefing" at the top
st.markdown('<h1 class="nyt-heading" style="font-size: 2.2rem; margin-top: 0; margin-bottom: 15px;">Today\'s Personalized Briefing</h1>', unsafe_allow_html=True)

# Then check if we should display video/audio content
if "show_video" in st.session_state and st.session_state.show_video:
    # Display success message right after masthead
    st.success("Your personalized briefing is ready!")
    
    video_path = st.session_state.video_path
    audio_path = st.session_state.audio_path
    
    # Display video/audio content with more compact styling
    if video_path and os.path.exists(video_path):
        # More compact video container with no extra padding
        st.markdown("""
        <style>
        /* Make video more compact */
        .stVideo {
            margin-bottom: 0 !important;
        }
        .stVideo video {
            max-height: 380px !important;
        }
        /* Remove extra bar below video */
        .stVideo [data-testid="stVerticalBlock"] {
            gap: 0 !important;
        }
        /* Remove extra padding */
        .main .block-container {
            padding-top: 0.5rem !important;
        }
        /* Make download section more compact */
        .download-section {
            margin: 10px 0 !important;
            padding: 10px !important;
        }
        /* Make success message more compact */
        [data-testid="stAlert"] {
            margin-bottom: 10px !important;
            padding: 8px !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Display video directly - no title needed since we have the main heading above
        st.video(video_path)
        
        # Download Options - more compact
        st.markdown('<div class="download-section" style="margin-top: 5px; padding: 10px;">', unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown('<div style="padding: 0; text-align: center;">', unsafe_allow_html=True)
            st.download_button(
                label="DOWNLOAD VIDEO",
                data=open(video_path, "rb"),
                file_name="sonicpress_news.mp4",
                mime="video/mp4",
                use_container_width=True
            )
            st.markdown('<div style="font-size: 0.8rem; color: #666; margin-top: 2px;">MP4 format</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        if audio_path and os.path.exists(audio_path):
            with col2:
                st.markdown('<div style="padding: 0; text-align: center;">', unsafe_allow_html=True)
                st.download_button(
                    label="DOWNLOAD AUDIO",
                    data=open(audio_path, "rb"),
                    file_name="sonicpress_news.mp3",
                    mime="audio/mp3",
                    use_container_width=True
                )
                st.markdown('<div style="font-size: 0.8rem; color: #666; margin-top: 2px;">MP3 format</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
    elif audio_path and os.path.exists(audio_path):
        st.audio(audio_path)
        
        # Download Options - more compact
        st.markdown('<div class="download-section" style="margin-top: 5px; padding: 10px;">', unsafe_allow_html=True)
        
        st.download_button(
            label="DOWNLOAD AUDIO",
            data=open(audio_path, "rb"),
            file_name="sonicpress_news.mp3",
            mime="audio/mp3",
            use_container_width=True
        )
        st.markdown('<div style="font-size: 0.8rem; color: #666; margin-top: 2px; text-align: center;">MP3 format</div>', unsafe_allow_html=True)
        
        st.markdown('</div>', unsafe_allow_html=True)

# Create placeholders for progress and results
progress_container = st.container()
headlines_container = st.container()  # Container for headlines and highlights

# If user clicked the "Compile My Headlines" button
if compile_button:
    if not categories or (use_custom_topic and not custom_query and not additional_cats):
        st.warning("Please enter a topic or select categories in the sidebar.")
    else:
        # First check API connectivity
        with progress_container:
            progress_bar = st.progress(0)
            status_placeholder = st.empty()
            status_placeholder.info("Starting your personalized news briefing...")
            
            # Skip API connectivity check since we're using the LiteLLM Proxy
            progress_bar.progress(5)

        try:
            # 1) Build preferences
            prefs = {
                "categories": categories,
                "voice_id": VOICE_OPTIONS[voice_choice]["id"],
                "num_results": num_results,
                "date": (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "min_image_width": 400,
                "min_image_height": 250,
                "use_placeholder": True
            }
            time.sleep(0.4)
            progress_bar.progress(15)
            
            # 2) Fetch & Summarize
            status_placeholder.info("Fetching relevant articles... (Powered by Exa)")
            summaries = agent.fetch_and_summarize(prefs)
            
            # If no articles found, try with a broader date range
            if not summaries:
                status_placeholder.info("No articles found. Trying with a broader date range...")
                broader_prefs = prefs.copy()
                broader_prefs["date"] = (datetime.now() - timedelta(days=days_ago * 2)).strftime("%Y-%m-%d")
                summaries = agent.fetch_and_summarize(broader_prefs)
                
                # If still no articles, try with an even broader date range
                if not summaries:
                    status_placeholder.info("Still no articles found. Trying with an even broader date range...")
                    broader_prefs["date"] = (datetime.now() - timedelta(days=days_ago * 4)).strftime("%Y-%m-%d")
                    summaries = agent.fetch_and_summarize(broader_prefs)
                    
                    # If still no articles, try with a more general query
                    if not summaries and len(categories) == 1:
                        status_placeholder.info("Still no articles found. Trying with a more general query...")
                        more_general_prefs = broader_prefs.copy()
                        # Add a more general category if the user provided a specific one
                        if categories[0] not in DEFAULT_CATEGORIES:
                            more_general_prefs["categories"] = ["Tech and Innovation"] + categories
                            summaries = agent.fetch_and_summarize(more_general_prefs)
                    
                    if not summaries:
                        status_placeholder.warning("No articles found. Try more general topics or a broader date range.")
                        st.stop()
            
            st.session_state.fetched_summaries = summaries
            time.sleep(0.4)
            progress_bar.progress(40)
            
            # 3) Generate Script
            status_placeholder.info("Composing your news script... (Powered by Mistral AI)")
            news_script = agent.generate_news_script(summaries, {})
            st.session_state.news_script = news_script
            time.sleep(0.4)
            progress_bar.progress(60)
            
            # 4) Convert to Speech
            status_placeholder.info("Recording voice narration... (Powered by ElevenLabs)")
            audio_path = agent.text_to_speech(news_script, voice_id=VOICE_OPTIONS[voice_choice]["id"])
            st.session_state.audio_path = audio_path
            time.sleep(0.4)
            progress_bar.progress(80)
            
            # 5) Generate Video
            status_placeholder.info("Finalizing your news video... (Powered by MoviePy)")
            os.makedirs("output", exist_ok=True)
            video_path = agent.generate_video(news_script, audio_path)
            st.session_state.video_path = video_path
            time.sleep(0.4)
            progress_bar.progress(100)
            
            # Clear the progress container and show success message
            progress_container.empty()
            
            # Set a flag in session state to indicate we should show the video
            st.session_state.show_video = True
            
            # Force a rerun to display the video at the top
            st.rerun()

        except Exception as e:
            progress_container.error(f"Something went wrong: {e}")

# Display Headlines & Highlights when summaries exist
if st.session_state.fetched_summaries:
    # Better organized headlines section with clearer visual hierarchy
    st.markdown('<div class="section-divider" style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    st.markdown('<h2 class="nyt-heading" style="font-size: 1.8rem; margin-top: 20px;">Headlines & Highlights</h2>', unsafe_allow_html=True)
    
    for cat_data in st.session_state.fetched_summaries:
        st.markdown(f'<h3 style="font-family: \'nyt-cheltenham\', georgia; font-size: 1.6rem; margin-top: 25px; border-bottom: 1px solid #e2e2e2; padding-bottom: 8px; color: #333;">{cat_data["title"]}</h3>', unsafe_allow_html=True)
        
        # Create columns for articles (2 columns for better newspaper layout)
        articles = cat_data["articles"]
        if len(articles) > 1:
            # Use columns for multiple articles
            cols = st.columns(2)
            for i, article in enumerate(articles):
                with cols[i % 2]:
                    st.markdown(f"""
                    <div class="news-card">
                        <h4>{article['title']}</h4>
                        <p>{article['summary']}</p>
                        <a href="{article['source']}" target="_blank" class="source-link">
                            Continue reading at {urlparse(article['source']).netloc} →
                        </a>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            # Single column for single article
            for article in articles:
                st.markdown(f"""
                <div class="news-card">
                    <h4>{article['title']}</h4>
                    <p>{article['summary']}</p>
                    <a href="{article['source']}" target="_blank" class="source-link">
                        Continue reading at {urlparse(article['source']).netloc} →
                    </a>
                </div>
                """, unsafe_allow_html=True)

# Fun Fact "Note from the Editor"
st.markdown(f"""
<div class="editor-note">
    <strong>Note from the Editor:</strong> {random.choice(FUN_FACTS)}
</div>
""", unsafe_allow_html=True)

# Add "Powered by" section
st.markdown("""
<div style="margin-top: 40px; text-align: center; padding: 20px; border-top: 1px solid var(--nyt-border);">
    <p style="font-family: 'nyt-franklin', arial; font-size: 0.8rem; color: var(--nyt-medium-gray); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px;">Powered by</p>
    <div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 40px; margin-top: 15px;">
        <div style="text-align: center;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 1rem;">Exa</div>
            <div style="font-size: 0.8rem; color: var(--nyt-medium-gray);">News Search & Retrieval</div>
        </div>
        <div style="text-align: center;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 1rem;">Mistral AI</div>
            <div style="font-size: 0.8rem; color: var(--nyt-medium-gray);">Script Generation</div>
        </div>
        <div style="text-align: center;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 1rem;">ElevenLabs</div>
            <div style="font-size: 0.8rem; color: var(--nyt-medium-gray);">Voice Synthesis</div>
        </div>
        <div style="text-align: center;">
            <div style="font-weight: bold; margin-bottom: 5px; font-size: 1rem;">MoviePy</div>
            <div style="font-size: 0.8rem; color: var(--nyt-medium-gray);">Video Generation</div>
        </div>
    </div>
</div>
""", unsafe_allow_html=True)
