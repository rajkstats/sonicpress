import streamlit as st
import time
import random
import os
from urllib.parse import urlparse
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load .env variables (for agent credentials)
load_dotenv(override=True)

# Import your NewsAgent (ensure agentic_news is installed or adjust as needed)
from agentic_news.agent import NewsAgent

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
    padding: 1rem 1.5rem !important;
    margin: 1rem 0 !important;
    transition: all 0.3s ease !important;
    border: none !important;
    font-size: 1.05rem !important;
    letter-spacing: 0.5px !important;
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
}
.news-card:hover {
    background-color: var(--nyt-light-gray);
}
.news-card h4 {
    font-family: "nyt-cheltenham", georgia, "times new roman", times, serif;
    font-weight: bold;
    font-size: 1.2rem;
    margin-bottom: 0.5rem;
}
.news-card p {
    font-size: 1rem;
    line-height: 1.5;
    color: var(--nyt-dark-gray);
}

/* Source link */
.source-link {
    display: inline-block;
    font-family: "nyt-franklin", arial, helvetica, sans-serif;
    font-size: 0.8em;
    color: var(--nyt-dark-gray);
    text-decoration: none;
    margin-top: 5px;
    border-bottom: 1px dotted var(--nyt-dark-gray);
}
.source-link:hover {
    text-decoration: underline;
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
}

/* Download section */
.download-section {
    background-color: var(--nyt-light-gray);
    padding: 15px;
    margin: 20px 0;
    border-top: 1px solid var(--nyt-border);
    border-bottom: 1px solid var(--nyt-border);
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

st.sidebar.markdown('<h2 style="margin-bottom:0;">THE SONICPRESS TIMES</h2>', unsafe_allow_html=True)
st.sidebar.caption("_Digital Edition_")
st.sidebar.markdown("---")

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

# Main call-to-action button in sidebar
compile_button = st.sidebar.button("📜 Compile My Headlines")

################################################################################
# MASTHEAD (TOP OF MAIN PAGE)
################################################################################

st.markdown(f"""
<div class="masthead">
    <div class="masthead-title">The SonicPress Times</div>
    <div class="masthead-date">{datetime.now().strftime("%A, %B %d, %Y")}</div>
</div>
""", unsafe_allow_html=True)

################################################################################
# MAIN CONTENT
################################################################################

# Show chosen topics at top (optional)
if categories:
    st.markdown('<span style="font-family: \'nyt-franklin\', arial; text-transform: uppercase; font-size: 0.85rem; color: #666;">Your Selected Topics</span>', unsafe_allow_html=True)
    cat_tags = "".join(f'<span class="category-tag">{cat}</span>' for cat in categories)
    st.markdown(f"{cat_tags}", unsafe_allow_html=True)
    st.write("")

# A headline
st.header("Today's Personalized Briefing")

# If user clicked the "Compile My Headlines" button
if compile_button:
    if not categories or (use_custom_topic and not custom_query and not additional_cats):
        st.warning("Please enter a topic or select categories in the sidebar.")
    else:
        # Show a progress bar
        progress_bar = st.progress(0)
        st.info("Gathering your personalized news...")

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
            st.info("Fetching relevant articles...")
            summaries = agent.fetch_and_summarize(prefs)
            if not summaries:
                st.warning("No articles found. Try more general topics or a broader date range.")
                st.stop()

            st.session_state.fetched_summaries = summaries
            time.sleep(0.4)
            progress_bar.progress(40)

            # 3) Generate Script
            st.info("Composing your news script...")
            news_script = agent.generate_news_script(summaries, {})
            st.session_state.news_script = news_script
            time.sleep(0.4)
            progress_bar.progress(60)

            # 4) Convert to Speech
            st.info("Recording voice narration...")
            audio_path = agent.text_to_speech(news_script, voice_id=VOICE_OPTIONS[voice_choice]["id"])
            st.session_state.audio_path = audio_path
            time.sleep(0.4)
            progress_bar.progress(80)

            # 5) Generate Video
            st.info("Finalizing your news video...")
            os.makedirs("output", exist_ok=True)
            video_path = agent.generate_video(news_script, audio_path)
            st.session_state.video_path = video_path
            time.sleep(0.4)
            progress_bar.progress(100)
            st.success("Your personalized briefing is ready!")
        except Exception as e:
            st.error(f"Something went wrong: {e}")

# If results exist in session state, display them
video_path = st.session_state.video_path
audio_path = st.session_state.audio_path

if video_path and os.path.exists(video_path):
    st.subheader("Your News Video")
    st.markdown('<div class="media-block">', unsafe_allow_html=True)
    st.video(video_path)
    st.markdown('</div>', unsafe_allow_html=True)
elif audio_path and os.path.exists(audio_path):
    st.subheader("Your News Audio")
    st.markdown('<div class="media-block">', unsafe_allow_html=True)
    st.audio(audio_path)
    st.markdown('</div>', unsafe_allow_html=True)

# Download Options
if (video_path and os.path.exists(video_path)) or (audio_path and os.path.exists(audio_path)):
    st.markdown('<div class="download-section">', unsafe_allow_html=True)
    st.write("### Download Options")
    col1, col2 = st.columns(2)
    if video_path and os.path.exists(video_path):
        with col1:
            st.download_button(
                label="Download Video",
                data=open(video_path, "rb"),
                file_name="sonicpress_news.mp4",
                mime="video/mp4"
            )
    if audio_path and os.path.exists(audio_path):
        with col2:
            st.download_button(
                label="Download Audio",
                data=open(audio_path, "rb"),
                file_name="sonicpress_news.mp3",
                mime="audio/mp3"
            )
    st.markdown('</div>', unsafe_allow_html=True)

# Show article summaries
if st.session_state.fetched_summaries:
    st.subheader("Headlines & Highlights")
    for cat_data in st.session_state.fetched_summaries:
        st.markdown(f"### {cat_data['title']}")
        for article in cat_data["articles"]:
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
