import sys
import os
from pathlib import Path

# Add the docker directory to the path so we can import the patch
docker_path = str(Path(__file__).parent.parent / "docker")
sys.path.append(docker_path)

# Import the MoviePy patch to fix ImageMagick issues
try:
    import moviepy_patch
    print(f"Successfully imported MoviePy patch from {docker_path}")
except ImportError as e:
    print(f"Warning: MoviePy patch not found or error importing: {e}")

import io
import json
import asyncio
import requests
from datetime import datetime, timedelta
from google.cloud import storage
from pydub import AudioSegment
from exa_py import Exa
from litellm import completion as chat_completion

# Ensure PIL.Image.ANTIALIAS is available before importing MoviePy
from PIL import Image, UnidentifiedImageError
try:
    from PIL.Image import Resampling  # Import the newer Resampling enum
except ImportError:
    # Fallback for older PIL versions
    pass

# Ensure PIL.Image.ANTIALIAS is available
if not hasattr(Image, "ANTIALIAS"):
    try:
        # For newer PIL versions
        Image.ANTIALIAS = Image.Resampling.LANCZOS
        print("Set PIL.Image.ANTIALIAS to Image.Resampling.LANCZOS")
    except AttributeError:
        # For very old PIL versions
        Image.ANTIALIAS = Image.LANCZOS
        print("Set PIL.Image.ANTIALIAS to Image.LANCZOS")

# Import MoviePy components
print("Importing MoviePy components...")
from moviepy.editor import (
    ColorClip, TextClip, AudioFileClip,
    CompositeVideoClip, ImageClip
)
print("MoviePy components imported successfully")

import numpy as np
from proglog import ProgressBarLogger
import math
import re
from io import BytesIO
from urllib.parse import urlparse
import time

# Patch MoviePy's ImageClip to handle PIL.Image.ANTIALIAS deprecation
# This is a direct monkey patch approach that doesn't rely on accessing the original method
try:
    print("Applying patch for MoviePy's ImageClip.resize...")
    
    # Store the original method if we haven't already
    if not hasattr(ImageClip, '_original_resize'):
        # Define a completely new resize method
        def patched_resize(self, newsize=None, height=None, width=None, apply_to_mask=True):
            """
            Resizes the clip to the given dimensions. Accepts float numbers.
            
            This is a patched version that handles PIL.Image.ANTIALIAS deprecation.
            """
            # Ensure PIL.Image.ANTIALIAS is available
            if not hasattr(Image, "ANTIALIAS"):
                try:
                    # For newer PIL versions
                    Image.ANTIALIAS = Image.Resampling.LANCZOS
                except AttributeError:
                    # For very old PIL versions
                    Image.ANTIALIAS = Image.LANCZOS
            
            # Implementation based on the original resize method
            w, h = self.size
            
            if newsize:
                # Handle case where newsize might be a tuple
                if isinstance(newsize, tuple):
                    w2, h2 = newsize
                else:
                    w2 = newsize[0] if isinstance(newsize, (list, tuple)) else newsize
                    h2 = newsize[1] if isinstance(newsize, (list, tuple)) and len(newsize) > 1 else h * w2 / w
            else:
                if width:
                    w2 = width
                    h2 = w2 * h / w
                elif height:
                    h2 = height
                    w2 = w * h2 / h
                else:
                    raise ValueError("Either newsize, width, or height must be provided")
            
            # Make sure the size is integer
            try:
                w2 = int(w2)
                h2 = int(h2)
            except (ValueError, TypeError) as e:
                print(f"Error converting size to integer: w2={w2}, h2={h2}, error={e}")
                # Fallback to original size if conversion fails
                w2, h2 = w, h
            
            # Ensure minimum size
            w2 = max(1, w2)
            h2 = max(1, h2)
            
            # Actual resizing using PIL
            try:
                img_resized = self.img.resize((w2, h2), Image.ANTIALIAS)
            except Exception as e:
                print(f"Error resizing image: {e}")
                # Fallback to nearest neighbor if ANTIALIAS fails
                img_resized = self.img.resize((w2, h2))
            
            # Create a new clip with the resized image
            new_clip = self.copy()
            new_clip.img = img_resized
            new_clip.size = (w2, h2)
            
            if apply_to_mask and self.mask:
                try:
                    new_clip.mask = self.mask.resize((w2, h2))
                except Exception as e:
                    print(f"Error resizing mask: {e}")
                    # If mask resize fails, create a new mask of the right size
                    new_clip.mask = None
            
            return new_clip
        
        # Save the original method and apply our patch
        ImageClip._original_resize = getattr(ImageClip, 'resize', None)
        ImageClip.resize = patched_resize
        print("Applied patch to MoviePy's ImageClip.resize method")
    else:
        print("MoviePy's ImageClip.resize already patched")
except Exception as e:
    print(f"Failed to apply patch to ImageClip.resize: {e}")

from .config import (
    EXA_API_KEY,
    ELEVENLABS_API_KEY,
    ELEVENLABS_BASE_URL,
    GCS_BUCKET_NAME,
    FUNCTION_DEFINITIONS as functions_definitions
)
from .providers import LiteLLMProvider, Message
from .utils.logger import Logger

logger = Logger()
action_model = LiteLLMProvider("large")

class NewsAgent:
    def __init__(self, save_logs=True):
        self.messages = []  # Agent memory
        self.state = {}
        self.exa = Exa(EXA_API_KEY)

        if save_logs:
            logger.log_file = "news_agent_log.html"

    def get_preferences(self):
        """
        Example: fetch user's categories, voice ID, etc.
        """
        preferences = {
            "categories": ["Tech and Innovation"],
            "voice_id": '9BWtsMINqrJLrRacOk9x',
            "date": "2023-10-01",
        }
        print("Retrieved Preferences:", preferences)
        return preferences

    def fetch_and_summarize(self, preferences, model="mistral/mistral-small-latest"):
        """Fetch and summarize news articles in one pass using Exa and summarizer."""
        try:
            if isinstance(preferences, str):
                preferences = json.loads(preferences)

            search_results = []
            
            for category in preferences["categories"]:
                # Add retry logic for rate limit errors
                max_retries = 3
                retry_delay = 2  # seconds
                
                for retry_count in range(max_retries):
                    try:
                        query_response = chat_completion(
                            messages=[
                                {
                                    "role": "system",
                                    "content": "Generate a search query in English only. Respond with ONLY the query text."
                                },
                                {"role": "user", "content": f"Latest news about: {category}"}
                            ],
                            model=model,
                            temperature=0.7
                        )
                        search_query = query_response.choices[0].message.content.strip()
                        print(f"\nSearching for: {search_query}")
                        break  # Success, exit retry loop
                    except Exception as e:
                        if "rate limit" in str(e).lower() and retry_count < max_retries - 1:
                            print(f"Rate limit error, retrying in {retry_delay} seconds... ({retry_count + 1}/{max_retries})")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            # If it's not a rate limit error or we've exhausted retries, re-raise
                            raise
                
                # Convert user-provided date (like "2023-10-01") to datetime object
                # or fallback to last 7 days if 1 day is empty
                date_str = preferences.get("date")
                if date_str:
                    # e.g., user wants news from <date_str> to now
                    start_date = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    # fallback
                    start_date = datetime.now() - timedelta(days=7)

                # Add retry logic for Exa API calls
                max_exa_retries = 3
                exa_retry_delay = 2  # seconds
                
                for exa_retry_count in range(max_exa_retries):
                    try:
                        # You can pass an explicit 'livecrawl' param if needed:
                        # e.g., livecrawl="always" to force Exa to re-fetch
                        # But note it's slower
                        search_response = self.exa.search_and_contents(
                            search_query,
                            text=True,
                            num_results=preferences.get("num_results", 3),  # Use user preference with default of 3
                            start_published_date=start_date.strftime("%Y-%m-%d"),
                            # Remove category restriction to get more diverse results
                            # category='news',
                            # livecrawl="auto",   # or "always", "never"
                        )
                        break  # Success, exit retry loop
                    except Exception as e:
                        if ("rate limit" in str(e).lower() or "429" in str(e)) and exa_retry_count < max_exa_retries - 1:
                            print(f"Exa API rate limit error, retrying in {exa_retry_delay} seconds... ({exa_retry_count + 1}/{max_exa_retries})")
                            time.sleep(exa_retry_delay)
                            exa_retry_delay *= 2  # Exponential backoff
                        else:
                            # If it's not a rate limit error or we've exhausted retries, re-raise
                            raise

                summarized_articles = []
                for result in search_response.results:
                    if not result.text:
                        continue

                    # Add retry logic for summarization
                    max_summary_retries = 3
                    summary_retry_delay = 2  # seconds
                    
                    for summary_retry_count in range(max_summary_retries):
                        try:
                            summary_response = chat_completion(
                                messages=[
                                    {
                                        "role": "system",
                                        "content": """You are a news summarizer. Create a single-sentence news summary that:
                                                - Uses exactly 20-30 words
                                                - No markdown, bullets, or special formatting
                                                - Simple present tense
                                                - Focus on the single most important fact
                                                - Must be in plain text format
                                                - Must be in English
                                                """
                                    },
                                    {
                                        "role": "user",
                                        "content": result.text
                                    }
                                ],
                                model=model,
                                temperature=0.7
                            )
                            
                            # Determine content type based on URL and content
                            content_type = "general"  # Default content type
                            url = result.url.lower()
                            
                            # News sites typically have /news/ in URL or are known domains
                            if ("/news/" in url or 
                                any(domain in url for domain in ["cnn.com", "bbc.com", "reuters.com", "nytimes.com", 
                                                               "theverge.com", "techcrunch.com", "wired.com"])):
                                content_type = "news"
                            
                            # Documentation pages
                            elif ("/docs/" in url or "/documentation/" in url or 
                                 any(domain in url for domain in ["docs.github.com", "readthedocs.io", "docs.python.org"])):
                                content_type = "documentation"
                            
                            # Reference sites like Wikipedia
                            elif "wikipedia.org" in url or "investopedia.com" in url:
                                content_type = "reference"
                            
                            # Social media
                            elif any(domain in url for domain in ["twitter.com", "x.com", "linkedin.com", "facebook.com", 
                                                                "reddit.com", "medium.com", "substack.com"]):
                                content_type = "social"
                            
                            # Video content
                            elif any(domain in url for domain in ["youtube.com", "vimeo.com", "twitch.tv"]):
                                content_type = "video"
                            
                            # Log the content type classification
                            print(f"Classified {result.title[:30]}... as {content_type}")
                            
                            summarized_articles.append({
                                "title": result.title,
                                "summary": summary_response.choices[0].message.content.strip(),
                                "source": result.url,
                                "date": getattr(result, 'published_date', None),
                                "content_type": content_type  # Add content type to the article data
                            })
                            break  # Success, exit retry loop
                        except Exception as e:
                            if "rate limit" in str(e).lower() and summary_retry_count < max_summary_retries - 1:
                                print(f"Rate limit error during summarization, retrying in {summary_retry_delay} seconds... ({summary_retry_count + 1}/{max_summary_retries})")
                                time.sleep(summary_retry_delay)
                                summary_retry_delay *= 2  # Exponential backoff
                            else:
                                # If it's not a rate limit error or we've exhausted retries, re-raise
                                raise
                
                if summarized_articles:
                    search_results.append({
                        "title": category,
                        "query": search_query,
                        "articles": summarized_articles
                    })
            
            # Store the results in self.state for later use in generate_video
            self.state['summaries'] = search_results
            
            return search_results

        except Exception as e:
            print(f"Error fetching and summarizing news: {str(e)}")
            return []

    def generate_news_script(self, summarized_results, preferences,
                             model="mistral/mistral-small-latest", temperature=0.7):
        """Generate a final news script from summaries."""
        try:
            total_articles = sum(len(cat['articles']) for cat in summarized_results)

            system_message = (
                "You are a professional news anchor. Create a natural, conversational news brief.\n"
                "Format:\n"
                "1. Start: 'Here are your news highlights'\n"
                "2. Body: One clear sentence per news item. Integrate sources naturally.\n"
                "3. End: 'That's your update'\n\n"
                "Important:\n"
                "- Use natural speech patterns\n"
                "- No formatting, bullets, or special characters\n"
                "- No topic headers or categories\n"
                "- Just plain, flowing text\n"
                "- Connect stories smoothly"
            )

            key_points = []
            for category in summarized_results:
                if category['articles']:
                    for article in category['articles']:
                        key_points.append(
                            f"Topic: {category['title']}\n"
                            f"Source: {article['source']}\n"
                            f"Summary: {article['summary']}"
                        )

            combined_text = "\n\n".join(key_points)

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": combined_text}
            ]

            response = chat_completion(
                messages=messages,
                model=model,
                temperature=temperature
            )

            script = response.choices[0].message.content.strip()
            print("\nGenerated News Script:")
            print("-" * 80)
            print(script)
            print("-" * 80)

            return script

        except Exception as e:
            print(f"Error generating news script: {str(e)}")
            return "Here are your news highlights. We're experiencing technical difficulties with today's update. That's your update."

    def generate_speech(self, text: str, voice_id: str,
                        model_id: str = "eleven_multilingual_v2",
                        stability: float = 0.71,
                        similarity_boost: float = 0.85,
                        style: float = 0.35,
                        speed: float = 1.0,
                        output_format: str = "mp3_44100_128") -> bytes:
        """Convert text to speech using ElevenLabs with advanced settings."""
        url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}?output_format={output_format}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": stability,
                "similarity_boost": similarity_boost,
                "style": style,
                "use_speaker_boost": True
            }
        }

        if speed != 1.0:
            # Apply simple SSML for speed if desired
            text = f'<speak><prosody rate="{int((speed-1)*100)}%">{text}</prosody></speak>'
            data["text"] = text

        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"API Error {response.status_code}: {response.text}")

    def text_to_speech(self, user_text: str, voice_id: str,
                       model_id: str = "eleven_multilingual_v2") -> str:
        """Generate an MP3 from text using TTS."""
        try:
            audio_data = self.generate_speech(
                text=user_text,
                voice_id=voice_id,
                model_id=model_id
            )
            audio_stream = io.BytesIO(audio_data)
            audio = AudioSegment.from_file(audio_stream, format="mp3")

            output_path = "output_speech.mp3"
            audio.export(output_path, format="mp3")
            return output_path
        except Exception as e:
            print("Failed to generate speech:", str(e))
            raise

    def upload_audio(self, audio_file_path):
        """Upload audio file to GCS and return the URL."""
        try:
            bucket_name = GCS_BUCKET_NAME
            filename = os.path.basename(audio_file_path)
            gcs_directory = f'audio/{filename}'

            client = storage.Client()
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(gcs_directory)

            print(f"Uploading {audio_file_path} to GCS...")
            blob.upload_from_filename(audio_file_path)

            gcs_url = f"gs://{bucket_name}/{gcs_directory}"
            print("Uploaded file is available at:", gcs_url)
            return gcs_url

        except Exception as e:
            print(f"Failed to upload audio: {str(e)}")
            return None

    def call_function(self, name, arguments):
        """Helper to map function calls from the system to actual methods."""
        func_impl = getattr(self, name.lower(), None)
        if func_impl:
            try:
                processed_args = {}
                for key, value in arguments.items():
                    if isinstance(value, str):
                        try:
                            processed_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            processed_args[key] = value
                    else:
                        processed_args[key] = value

                # Example direct calls
                if name == 'summarize_article':
                    return func_impl(processed_args.get('article_data'))
                elif name == 'generate_news_script':
                    return func_impl(
                        processed_args.get('summarized_results'),
                        processed_args.get('preferences')
                    )
                elif name == 'text_to_speech':
                    return func_impl(
                        processed_args.get('user_text'),
                        processed_args.get('voice_id'),
                        processed_args.get('model_id')
                    )

                return func_impl(**processed_args) if processed_args else func_impl()
            except Exception as e:
                print(f"Error executing function: {str(e)}")
                return None
        else:
            return "Function not implemented."

    def run(self, instruction):
        """Example run method that orchestrates multi-step calls."""
        self.messages.append(Message(f"OBJECTIVE: {instruction}"))
        system_message = Message(
            "You are a news assistant that must complete steps in order:\n"
            "1. get_preferences\n2. fetch_and_summarize\n3. generate_news_script\n4. text_to_speech\n"
            "5. upload_audio\n6. generate_video\n",
            role="system"
        )

        content, tool_calls = action_model.call(
            [
                system_message,
                *self.messages,
                Message("Let's complete these steps one by one.")
            ],
            functions_definitions
        )

        # Simplified handling of steps:
        if content:
            print(f"\nTHOUGHT: {content}")
            self.messages.append(Message(logger.log(f"THOUGHT: {content}", "blue")))

        for tool_call in tool_calls:
            name = tool_call.get("name")
            parameters = tool_call.get("parameters", {})
            logger.log(f"ACTION: {name} {str(parameters)}", "red")
            result = self.call_function(name, parameters)
            self.state[name] = result
            self.messages.append(Message(
                f"Step completed: {name}\nResult: {json.dumps(result)}",
                role="assistant"
            ))

            # Next step
            content, next_tool_calls = action_model.call(
                [
                    system_message,
                    *self.messages,
                    Message("What's the next step we should take?")
                ],
                functions_definitions
            )
            if content:
                print(f"\nTHOUGHT: {content}")
                self.messages.append(Message(logger.log(f"THOUGHT: {content}", "blue")))

            if next_tool_calls:
                tool_calls.extend(next_tool_calls)

        # Check if we need to generate a video
        if "text_to_speech" in self.state and "upload_audio" in self.state:
            if "generate_video" not in self.state:
                print("\nGenerating video from audio and script...")
                script = self.state.get("generate_news_script", "")
                audio_path = self.state.get("text_to_speech", "")
                if script and audio_path:
                    video_path = self.generate_video(script, audio_path)
                    self.state["generate_video"] = video_path
                    print(f"Video generated: {video_path}")

        return self.state.get("upload_audio")

    def generate_video(self, script: str, audio_path: str, output_path: str = "output/news_video.mp4") -> str:
        """
        Generate a news video using the script, images, and audio narration.
        Fully self-contained version:
        - Fetches images for each article inline.
        - Builds a single composite video with an intro, ticker, article segments, and outro.
        - Cleans up all temp images at the end.
        """
        import os
        import re
        import requests
        from io import BytesIO
        from urllib.parse import urlparse

        from moviepy.editor import (
            ColorClip, TextClip, AudioFileClip,
            CompositeVideoClip, ImageClip
        )
        from PIL import Image, UnidentifiedImageError

        try:
            # ---------------------------------------------------------------------
            # 1) Load the narration audio
            # ---------------------------------------------------------------------
            audio = AudioFileClip(audio_path)
            total_duration = audio.duration

            # ---------------------------------------------------------------------
            # 2) Prepare background
            # ---------------------------------------------------------------------
            width, height = 1280, 720
            background_color = (0, 20, 40)  # dark navy
            background = ColorClip((width, height), color=background_color).set_duration(total_duration)

            # Define intro and outro durations early
            intro_duration = 2  # seconds
            outro_duration = 3  # seconds
            
            # ---------------------------------------------------------------------
            # 3) Gather articles from self.state["summaries"]
            # ---------------------------------------------------------------------
            summaries = self.state.get('summaries', [])
            article_data = []
            for cat in summaries:
                for art in cat["articles"]:
                    article_data.append({
                        "title": art["title"],
                        "summary": art["summary"],
                        "url": art["source"],
                    })

            # Ensure we have at least one article
            if not article_data and summaries:
                print("WARNING: No article data found in summaries, creating placeholder")
                article_data = [{
                    "title": "News Update",
                    "summary": script if script else "No content available",
                    "url": ""
                }]
            
            # ---------------------------------------------------------------------
            # 4) Parse script into chunks
            # ---------------------------------------------------------------------
            lines = script.split("\n")
            article_text_chunks = []
            
            # Improved script parsing
            # First, join all lines and remove intro/outro phrases
            full_text = " ".join(lines)
            clean_text = full_text.strip()
            
            # Remove standard intro/outro phrases
            intro_patterns = ["here are your news highlights", "here's your news update", "welcome to your news update"]
            outro_patterns = ["that's your update", "that's all for today", "thanks for listening"]
            
            # Track the start and end positions of intro/outro for timing calculations
            intro_length = 0
            outro_length = 0
            
            for pattern in intro_patterns:
                if clean_text.lower().startswith(pattern):
                    intro_length = len(pattern)
                    clean_text = clean_text[len(pattern):].strip()
                    print(f"Removed intro phrase: '{pattern}'")
            
            for pattern in outro_patterns:
                if clean_text.lower().endswith(pattern):
                    outro_length = len(pattern)
                    clean_text = clean_text[:-len(pattern)].strip()
                    print(f"Removed outro phrase: '{pattern}'")
            
            # Split into sentences (simple approach)
            sentences = re.split(r'(?<=[.!?])\s+', clean_text)
            sentences = [s.strip() for s in sentences if s.strip()]
            
            print(f"Extracted {len(sentences)} sentences from script")
            
            # Try to match sentences to articles using title keywords
            # This helps ensure that images match the content being discussed
            if sentences and article_data:
                print("Attempting to match sentences to articles using keyword matching...")
                
                # Create a mapping of articles to their sentences
                article_to_sentences = {i: [] for i in range(len(article_data))}
                unmatched_sentences = []
                
                # First pass: try to match sentences to articles based on keywords in titles
                for sentence in sentences:
                    sentence_lower = sentence.lower()
                    best_match = None
                    best_score = 0
                    
                    for i, article in enumerate(article_data):
                        # Extract keywords from title (simple approach: split by spaces and remove common words)
                        title_words = set(article['title'].lower().split())
                        # Remove common words
                        title_words = {w for w in title_words if len(w) > 3 and w not in 
                                      {'the', 'and', 'that', 'this', 'with', 'from', 'have', 'will'}}
                        
                        # Count how many title words appear in the sentence
                        score = sum(1 for word in title_words if word in sentence_lower)
                        
                        # If we found a better match, update
                        if score > best_score:
                            best_score = score
                            best_match = i
                    
                    # If we found a good match, add the sentence to that article
                    if best_score > 0:
                        article_to_sentences[best_match].append(sentence)
                        print(f"  Matched sentence to article #{best_match+1} (score: {best_score}): {sentence[:50]}...")
                    else:
                        unmatched_sentences.append(sentence)
                        print(f"  No match found for sentence: {sentence[:50]}...")
                
                # Second pass: distribute unmatched sentences
                if unmatched_sentences:
                    print(f"Distributing {len(unmatched_sentences)} unmatched sentences...")
                    
                    # Find articles with no sentences and prioritize them
                    empty_articles = [i for i, sentences in article_to_sentences.items() if not sentences]
                    
                    if empty_articles:
                        # Distribute sentences evenly among empty articles first
                        sentences_per_article = len(unmatched_sentences) // len(empty_articles)
                        remainder = len(unmatched_sentences) % len(empty_articles)
                        
                        start_idx = 0
                        for i, article_idx in enumerate(empty_articles):
                            # Add one extra sentence to early articles if we have remainder
                            extra = 1 if i < remainder else 0
                            chunk_size = sentences_per_article + extra
                            end_idx = start_idx + chunk_size
                            
                            if end_idx <= len(unmatched_sentences):
                                article_to_sentences[article_idx].extend(unmatched_sentences[start_idx:end_idx])
                                start_idx = end_idx
                        
                        # If we still have unmatched sentences, distribute them evenly among all articles
                        remaining_unmatched = unmatched_sentences[start_idx:]
                        if remaining_unmatched:
                            for i, sentence in enumerate(remaining_unmatched):
                                article_idx = i % len(article_data)
                                article_to_sentences[article_idx].append(sentence)
                    else:
                        # If all articles have some sentences, distribute remaining evenly
                        for i, sentence in enumerate(unmatched_sentences):
                            article_idx = i % len(article_data)
                            article_to_sentences[article_idx].append(sentence)
                
                # Now create text chunks from the matched sentences
                article_text_chunks = []
                for i in range(len(article_data)):
                    if i in article_to_sentences and article_to_sentences[i]:
                        chunk = " ".join(article_to_sentences[i])
                        article_text_chunks.append(chunk)
                        print(f"Article #{i+1} text chunk: {chunk[:50]}..." if len(chunk) > 50 else chunk)
                    else:
                        # If no sentences were matched, use the article summary as fallback
                        article_text_chunks.append(article_data[i]['summary'])
                        print(f"Article #{i+1} using summary as fallback: {article_data[i]['summary']}")
            else:
                # Fallback to the original approach if matching fails
                print("Using original approach to group sentences...")
                # Group sentences into chunks based on article count
                if sentences and article_data:
                    # If we have more sentences than articles, try to group them
                    if len(sentences) > len(article_data):
                        sentences_per_article = len(sentences) // len(article_data)
                        remainder = len(sentences) % len(article_data)
                        
                        print(f"Grouping {len(sentences)} sentences into {len(article_data)} chunks")
                        print(f"Using ~{sentences_per_article} sentences per article")
                        
                        article_text_chunks = []
                        start_idx = 0
                        
                        for i in range(len(article_data)):
                            # Add one extra sentence to early chunks if we have remainder
                            extra = 1 if i < remainder else 0
                            chunk_size = sentences_per_article + extra
                            end_idx = start_idx + chunk_size
                            
                            if end_idx <= len(sentences):
                                chunk = " ".join(sentences[start_idx:end_idx])
                                article_text_chunks.append(chunk)
                                start_idx = end_idx
                        
                        print(f"Created {len(article_text_chunks)} text chunks from sentences")
                    else:
                        # If we have fewer or equal sentences to articles, use each sentence as a chunk
                        article_text_chunks = sentences
                        print(f"Using {len(article_text_chunks)} individual sentences as text chunks")
            
            # Fallback: if we still don't have any chunks, use the whole script
            if not article_text_chunks and script:
                print("No article chunks extracted, using entire script as one chunk")
                article_text_chunks = [clean_text if clean_text else script]
            
            # Add word count function back
            def word_count(s): 
                return len(s.split())

            total_words = sum(word_count(ch) for ch in article_text_chunks)
            print(f"Total words across all chunks: {total_words}")

            # Only handle as many articles as we have matching lines
            min_count = min(len(article_data), len(article_text_chunks))
            
            # Ensure we have at least one segment to display
            if min_count == 0 and (article_data or article_text_chunks):
                print("WARNING: min_count is 0 but we have content. Using available content.")
                min_count = max(len(article_data), len(article_text_chunks))
                
                # If we have articles but no text chunks, use summaries as text chunks
                if not article_text_chunks and article_data:
                    print("Using article summaries as text chunks")
                    article_text_chunks = [art["summary"] for art in article_data]
                
                # If we have text chunks but no articles, create placeholder articles
                if not article_data and article_text_chunks:
                    print("Creating placeholder articles from text chunks")
                    article_data = [{"title": f"News Item #{i+1}", "summary": chunk, "url": ""} 
                                   for i, chunk in enumerate(article_text_chunks)]
            
            # IMPORTANT FIX: If we have more articles than text chunks, use each article's summary as its text chunk
            if len(article_data) > len(article_text_chunks) and article_text_chunks:
                print(f"WARNING: More articles ({len(article_data)}) than text chunks ({len(article_text_chunks)})")
                print("Using article summaries to create additional text chunks")
                
                # Keep existing text chunks and add summaries for the remaining articles
                additional_chunks = [art["summary"] for art in article_data[len(article_text_chunks):]]
                article_text_chunks.extend(additional_chunks)
                
                # Update min_count to use all available articles
                min_count = len(article_data)
                print(f"Updated min_count to {min_count} to include all articles")
                
            # Calculate segment durations based on word count
            # This ensures that segments are proportional to their content
            segment_durations = []
            usable_duration = total_duration - (intro_duration + outro_duration)
            
            # First pass: calculate raw durations based on word count
            for i in range(min_count):
                chunk = article_text_chunks[i] if i < len(article_text_chunks) else ""
                wc = word_count(chunk)
                fraction = wc / total_words if total_words else 1.0 / min_count
                duration = fraction * usable_duration
                segment_durations.append(max(duration, 3.0))  # Minimum 3 seconds
            
            # Second pass: adjust durations to match total available time
            total_segment_duration = sum(segment_durations)
            if total_segment_duration > usable_duration:
                # Scale down proportionally if we exceed available time
                scale_factor = usable_duration / total_segment_duration
                segment_durations = [d * scale_factor for d in segment_durations]
                print(f"Scaled segment durations by {scale_factor:.2f} to fit available time")
            
            print("Segment durations:")
            for i, duration in enumerate(segment_durations):
                print(f"  Segment #{i+1}: {duration:.2f}s")

            # ---------------------------------------------------------------------
            # 5) Inline image fetching
            # ---------------------------------------------------------------------
            print("\n" + "-"*50)
            print("STEP 5: FETCHING IMAGES FOR ARTICLES")
            print("-"*50)
            
            def fetch_best_image_for(url):
                """Fetch an image for a given article URL using self.exa or HTML fallbacks."""
                print(f"  Fetching image for: {url}")
                best_image_url = None

                # (A) Use exa.get_contents if available
                try:
                    print("    Attempting Exa content fetch...")
                    content_resp = self.exa.get_contents(urls=[url])
                    if content_resp and hasattr(content_resp, "contents") and content_resp.contents:
                        for c in content_resp.contents:
                            if hasattr(c, "images") and c.images:
                                valid_imgs = [
                                    i for i in c.images
                                    if i.width >= 300 and i.height >= 200
                                ]
                                if valid_imgs:
                                    # pick the largest
                                    biggest = max(valid_imgs, key=lambda x: x.width * x.height)
                                    best_image_url = biggest.url
                                    print(f"    ✓ Found image via Exa: {biggest.width}x{biggest.height}")
                                    break
                except Exception as e:
                    print(f"    ✗ Exa content fetch failed: {e}")

                # (B) fallback: parse meta tags
                if not best_image_url:
                    try:
                        print("    Attempting HTML meta tag parsing...")
                        resp = requests.get(url, timeout=10)
                        if resp.status_code == 200:
                            patterns = [
                                r'<meta\s+(?:property|name)="(?:og:image|og:image:secure_url|twitter:image)"\s+content="([^"]+)"',
                                r'<img[^>]+src="([^"]+(?:jpg|jpeg|png|gif))"[^>]+(?:width|height)="[3-9]\d{2,}"'
                            ]
                            for pat in patterns:
                                matches = re.findall(pat, resp.text)
                                if matches:
                                    best_image_url = matches[0]
                                    if best_image_url.startswith("/"):
                                        # make absolute
                                        from urllib.parse import urlparse
                                        base = urlparse(url)
                                        best_image_url = f"{base.scheme}://{base.netloc}{best_image_url}"
                                    print(f"    ✓ Found image via HTML meta: {best_image_url[:50]}...")
                                    break
                    except Exception as e:
                        print(f"    ✗ Fallback meta parse failed: {e}")

                # (C) Attempt to download
                if best_image_url:
                    try:
                        print("    Downloading image...")
                        r = requests.get(best_image_url, timeout=15)
                        if r.status_code == 200:
                            with BytesIO(r.content) as buf:
                                try:
                                    pil_img = Image.open(buf).convert("RGB")
                                    print(f"    ✓ Image loaded: {pil_img.width}x{pil_img.height}")
                                    if pil_img.width < 10 or pil_img.height < 10:
                                        print("    ✗ Image too small, skipping.")
                                        return None
                                    os.makedirs("temp_images", exist_ok=True)
                                    img_path = f"temp_images/img_{abs(hash(url))}.png"
                                    pil_img.save(img_path)
                                    print(f"    ✓ Saved to: {img_path}")
                                    return img_path
                                except UnidentifiedImageError:
                                    print("    ✗ Unidentified image format.")
                                except Exception as e:
                                    print(f"    ✗ Error processing image: {e}")
                    except Exception as e:
                        print(f"    ✗ Could not download image: {e}")

                # No fallback image creation - just return None
                print("    ✗ No suitable image found")
                return None

            images_for_articles = []
            successful_images = 0
            failed_images = 0
            
            for i, art in enumerate(article_data):
                print(f"  Article #{i+1}: {art['title']}")
                path = fetch_best_image_for(art["url"])
                if path:
                    successful_images += 1
                else:
                    failed_images += 1
                images_for_articles.append(path)
            
            print(f"✓ Image fetching complete:")
            print(f"  - Total articles: {len(article_data)}")
            print(f"  - Successfully downloaded: {successful_images}")
            print(f"  - Failed to find images: {failed_images}")

            # ---------------------------------------------------------------------
            # 6) Build base clips
            # ---------------------------------------------------------------------
            print("\n" + "-"*50)
            print("STEP 6: BUILDING BASE VIDEO ELEMENTS")
            print("-"*50)
            
            all_clips = [background]

            # Logo top-left
            logo_text = TextClip(
                "SonicPress",
                fontsize=36,
                color="white",
                font="Arial-Bold",
                method="label"
            ).set_position((20, 20)).set_duration(total_duration)
            all_clips.append(logo_text)
            print("✓ Added logo text")

            # Intro (2 seconds)
            intro_text = TextClip(
                "SonicPress News",
                fontsize=70,
                color="white",
                font="Arial-Bold",
                method="caption"
            ).set_position("center").set_duration(intro_duration)
            all_clips.append(intro_text)
            print(f"✓ Added intro text ({intro_duration}s)")

            # Outro (last 3 seconds)
            outro_text = TextClip(
                "Thanks for watching!",
                fontsize=50,
                color="white",
                font="Arial-Bold",
                method="label"
            ).set_position("center") \
            .set_start(total_duration - outro_duration) \
            .set_duration(outro_duration)
            all_clips.append(outro_text)
            print(f"✓ Added outro text ({outro_duration}s)")

            # Ticker
            ticker_height = 60
            ticker_bg = ColorClip((width, ticker_height), color=(200, 50, 50)).set_duration(total_duration)
            ticker_y = height - ticker_height - 80
            ticker_bg = ticker_bg.set_position((0, ticker_y))
            all_clips.append(ticker_bg)
            print("✓ Added ticker background")

            # Calculate the safe area for content (avoid ticker overlap)
            safe_bottom_y = ticker_y - 40  # 40px margin above ticker
            
            ticker_titles = [a["title"] for a in article_data]
            ticker_text_content = " • ".join(ticker_titles) if ticker_titles else "No headlines"
            ticker_txt_clip = TextClip(
                ticker_text_content,
                fontsize=24,
                color="white",
                font="Arial-Bold"
            )
            tw, th = ticker_txt_clip.size

            def scroll_position(t):
                x = width - (width + tw) * (t / total_duration)
                return (x, ticker_y + (ticker_height - th) // 2)

            scrolling_ticker = ticker_txt_clip.set_duration(total_duration).set_position(scroll_position)
            all_clips.append(scrolling_ticker)
            print(f"✓ Added scrolling ticker with {len(ticker_titles)} headlines")
            print(f"✓ Safe bottom area: y < {safe_bottom_y}px")

            # ---------------------------------------------------------------------
            # 7) Article segments
            # ---------------------------------------------------------------------
            print("\n" + "-"*50)
            print("STEP 7: BUILDING ARTICLE SEGMENTS")
            print("-"*50)
            
            # Calculate start times for each segment based on durations
            segment_start_times = [intro_duration]
            for i in range(1, min_count):
                segment_start_times.append(segment_start_times[i-1] + segment_durations[i-1])
            
            print("Segment timing:")
            for i in range(min_count):
                end_time = segment_start_times[i] + segment_durations[i]
                print(f"  Segment #{i+1}: {segment_start_times[i]:.2f}s - {end_time:.2f}s (duration: {segment_durations[i]:.2f}s)")
            
            image_clips_added = 0
            headline_clips_added = 0
            summary_clips_added = 0
            
            # Ensure arrays are properly sized for iteration
            if len(article_text_chunks) < min_count:
                print(f"WARNING: Only {len(article_text_chunks)} text chunks for {min_count} segments")
                # Pad with empty strings if needed
                article_text_chunks.extend([""] * (min_count - len(article_text_chunks)))
                
            if len(article_data) < min_count:
                print(f"WARNING: Only {len(article_data)} articles for {min_count} segments")
                # Pad with placeholder data if needed
                article_data.extend([{"title": "News Update", "summary": "No content available", "url": ""}] 
                                   * (min_count - len(article_data)))
            
            print(f"Processing {min_count} segments with {len(article_data)} articles and {len(article_text_chunks)} text chunks")
            
            # Add debug timing indicators (small colored bars at the bottom of the screen)
            # This helps visualize segment transitions
            debug_timing = False  # Disabled - no timeline at bottom of video
            
            for i in range(min_count):
                chunk = article_text_chunks[i] if i < len(article_text_chunks) else ""
                article = article_data[i] if i < len(article_data) else {"title": f"News Item #{i+1}", "summary": chunk, "url": ""}
                
                # Use pre-calculated segment duration and start time
                segment_duration = segment_durations[i]
                start_time = segment_start_times[i]

                print(f"\nSegment #{i+1}:")
                print(f"  - Title: {article['title']}")
                print(f"  - Text chunk: {chunk[:50]}..." if len(chunk) > 50 else chunk)
                print(f"  - Start time: {start_time:.2f}s")
                print(f"  - Duration: {segment_duration:.2f}s")
                
                # HEADLINE (always at top)
                headline_clip = TextClip(
                    article['title'],
                    fontsize=34,
                    color="white",
                    font="Arial-Bold",
                    method="caption",
                    size=(width - 100, None),
                    align="center"
                ).set_position(("center", 80)) \
                .set_start(start_time) \
                .set_duration(segment_duration)
                all_clips.append(headline_clip)
                headline_clips_added += 1
                print(f"  ✓ Added headline text")

                # Image (only if available)
                img_path = images_for_articles[i] if i < len(images_for_articles) else None
                if img_path and os.path.exists(img_path):
                    try:
                        # Load the image using PIL first to avoid numpy array reference issues
                        pil_img = Image.open(img_path).convert("RGB")
                        # Create a fresh ImageClip from the PIL image
                        img_clip = ImageClip(np.array(pil_img))
                        
                        # Force max 600×338
                        iw, ih = img_clip.size
                        scale = min(600/iw, 338/ih) if (iw>600 or ih>338) else 1
                        new_w, new_h = int(iw*scale), int(ih*scale)
                        
                        # Resize using PIL instead of MoviePy's resize method
                        resized_pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                        img_clip = ImageClip(np.array(resized_pil_img))
                        
                        # Calculate positions for a structured layout
                        # 1. Headline at top (already positioned at y=80)
                        # 2. Image in upper half of screen
                        # 3. Summary in lower half of screen, above ticker
                        
                        # Position image in the upper part of the screen (below headline)
                        image_y = 150  # Fixed position below headline
                        img_clip = img_clip.set_position(("center", image_y)) \
                                        .set_start(start_time) \
                                        .set_duration(segment_duration)
                        all_clips.append(img_clip)
                        image_clips_added += 1
                        print(f"  ✓ Added image: {new_w}x{new_h} at y={image_y}")
                        
                        # Calculate maximum available height for summary
                        available_height = safe_bottom_y - (image_y + new_h)
                        
                        # If not enough space for summary (less than 120px), reduce image size
                        if available_height < 120:
                            print(f"  ⚠ Not enough space for summary (only {available_height}px available)")
                            # Use a smaller image size
                            scale_factor = 0.8  # Reduce to 80% of original size
                            new_w, new_h = int(new_w * scale_factor), int(new_h * scale_factor)
                            
                            # Remove the old clip from all_clips before adding the resized one
                            all_clips.pop()  # Remove the last added clip (the original image)
                            image_clips_added -= 1  # Decrement the counter since we removed a clip
                            
                            # Create a new resized clip using PIL
                            resized_pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)
                            img_clip = ImageClip(np.array(resized_pil_img))
                            img_clip = img_clip.set_position(("center", image_y)) \
                                            .set_start(start_time) \
                                            .set_duration(segment_duration)
                            all_clips.append(img_clip)
                            image_clips_added += 1
                            
                            print(f"  ✓ Resized image to {new_w}x{new_h} to make room for summary")
                            # Recalculate available height
                            available_height = safe_bottom_y - (image_y + new_h)
                        
                        # Place summary with fixed spacing from image
                        summary_y = image_y + new_h + 40  # 40px gap after image
                        
                        # Ensure summary doesn't overlap with ticker
                        if summary_y > safe_bottom_y - 100:  # Allow 100px for summary text
                            summary_y = safe_bottom_y - 100
                            print(f"  ⚠ Adjusted summary position to avoid ticker overlap")
                        
                        print(f"  - Image position: center, y={image_y}")
                        print(f"  - Image dimensions: {new_w}x{new_h}")
                        print(f"  - Summary position: center, y={summary_y}")
                        print(f"  - Available height for summary: {available_height}px")
                        print(f"  - Ticker position: y={ticker_y}")
                        
                        # Adjust font size based on available height
                        summary_font_size = 26  # Default font size
                        if available_height < 150:
                            summary_font_size = 22  # Smaller font if space is limited
                            print(f"  ⚠ Reduced summary font size to {summary_font_size} due to limited space")
                        
                        summary_clip = TextClip(
                            article['summary'],
                            fontsize=summary_font_size,
                            color="white",
                            font="Arial",
                            method="caption",
                            size=(width - 150, None),
                            align="center"
                        ).set_position(("center", summary_y)) \
                        .set_start(start_time) \
                        .set_duration(segment_duration)
                    except Exception as e:
                        print(f"  ✗ Error with image {img_path}: {e}")
                        # If image fails, center the summary
                        
                        # Calculate a good position for the summary when image loading fails
                        # Place it in the center of the screen, but above the ticker
                        center_y = (height / 2)
                        
                        # Ensure it doesn't overlap with the ticker
                        if center_y + 100 > safe_bottom_y:  # Allow 100px for summary text
                            center_y = safe_bottom_y - 150  # 150px above ticker
                        
                        print(f"  - Summary position (image failed): center, y={center_y}")
                        print(f"  - Ticker position: y={ticker_y}")
                        
                        summary_clip = TextClip(
                            article['summary'],
                            fontsize=28,
                            color="white",
                            font="Arial",
                            method="caption",
                            size=(width - 200, None),
                            align="center"
                        ).set_position(("center", center_y)) \
                        .set_start(start_time) \
                        .set_duration(segment_duration)
                else:
                    # No image - center the summary but avoid ticker
                    print(f"  ✗ No image available")
                    
                    # Calculate a good position for the summary when no image is present
                    # Place it in the center of the screen, but above the ticker
                    center_y = (height / 2)
                    
                    # Ensure it doesn't overlap with the ticker
                    if center_y + 100 > safe_bottom_y:  # Allow 100px for summary text
                        center_y = safe_bottom_y - 150  # 150px above ticker
                    
                    print(f"  - Summary position (no image): center, y={center_y}")
                    print(f"  - Ticker position: y={ticker_y}")
                    
                    summary_clip = TextClip(
                        article['summary'],
                        fontsize=28,
                        color="white",
                        font="Arial",
                        method="caption",
                        size=(width - 200, None),
                        align="center"
                    ).set_position(("center", center_y)) \
                    .set_start(start_time) \
                    .set_duration(segment_duration)
                
                all_clips.append(summary_clip)
                summary_clips_added += 1
                print(f"  ✓ Added summary text")
            
            print("\nArticle segments complete:")
            print(f"  - Total segments: {min_count}")
            print(f"  - Headlines added: {headline_clips_added}/{min_count}")
            print(f"  - Images added: {image_clips_added}/{min_count}")
            print(f"  - Summaries added: {summary_clips_added}/{min_count}")

            # ---------------------------------------------------------------------
            # 8) Compose final
            # ---------------------------------------------------------------------
            print("\n" + "-"*50)
            print("STEP 8: COMPOSITING FINAL VIDEO")
            print("-"*50)
            
            print(f"Total clips to composite: {len(all_clips)}")
            final_clip = CompositeVideoClip(all_clips).set_audio(audio)

            # Make sure output folder exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            print(f"Writing video to: {output_path}")
            print(f"This may take a while...")
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=4,
                preset="medium",
                bitrate="3000k"
            )

            final_clip.close()
            audio.close()
            print(f"Video rendering complete!")

            # ---------------------------------------------------------------------
            # 9) Cleanup
            # ---------------------------------------------------------------------
            print("\n" + "-"*50)
            print("STEP 9: CLEANING UP TEMPORARY FILES")
            print("-"*50)
            
            removed_count = 0
            for path in images_for_articles:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                        removed_count += 1
                    except:
                        pass
            print(f"Removed {removed_count} temporary image files")

            print("\n" + "="*80)
            print("VIDEO GENERATION SUMMARY")
            print("="*80)
            print(f"Total duration: {total_duration:.2f} seconds")
            print(f"Segments: {min_count}")
            print(f"Images: {successful_images} downloaded, {failed_images} missing")
            print(f"Output: {output_path}")
            print("="*80 + "\n")

            return output_path

        except Exception as e:
            print(f"Failed to generate video: {e}")
            raise