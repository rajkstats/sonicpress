import io
import os
import json
import asyncio
import requests
from datetime import datetime, timedelta
from google.cloud import storage
from pydub import AudioSegment
from exa_py import Exa
from litellm import completion as chat_completion
from moviepy.editor import (
    ColorClip, TextClip, AudioFileClip,
    CompositeVideoClip, ImageClip
)
from PIL import Image, UnidentifiedImageError
try:
    from PIL.Image import Resampling  # Import the newer Resampling enum
except ImportError:
    # Fallback for older PIL versions
    pass
import numpy as np
from proglog import ProgressBarLogger
import math
import re
from io import BytesIO
from urllib.parse import urlparse

# Patch MoviePy's ImageClip to handle PIL.Image.ANTIALIAS deprecation
# This needs to be done before any ImageClip is created
import moviepy.video.VideoClip as VideoClip
original_resize = VideoClip.ImageClip.resize

def patched_resize(self, newsize=None, height=None, width=None, apply_to_mask=True):
    """Patched resize method to handle PIL.Image.ANTIALIAS deprecation"""
    try:
        return original_resize(self, newsize, height, width, apply_to_mask)
    except AttributeError as e:
        if "ANTIALIAS" in str(e):
            # Monkey patch PIL.Image.ANTIALIAS at runtime
            if not hasattr(Image, "ANTIALIAS"):
                try:
                    # For newer PIL versions
                    Image.ANTIALIAS = Image.Resampling.LANCZOS
                except AttributeError:
                    # For very old PIL versions
                    Image.ANTIALIAS = Image.LANCZOS
            # Try again with the patched attribute
            return original_resize(self, newsize, height, width, apply_to_mask)
        else:
            raise

# Apply the patch
VideoClip.ImageClip.resize = patched_resize

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
            # If the 1-day window yields no results, broaden to 3 or 7 days
            # Or do it directly with preferences["date"] usage:
            #   start_published_date = preferences["date"]  # or a derived date
            # For demonstration, we use the same approach as original
            for category in preferences["categories"]:
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

                # Convert user-provided date (like "2023-10-01") to datetime object
                # or fallback to last 7 days if 1 day is empty
                date_str = preferences.get("date")
                if date_str:
                    # e.g., user wants news from <date_str> to now
                    start_date = datetime.strptime(date_str, "%Y-%m-%d")
                else:
                    # fallback
                    start_date = datetime.now() - timedelta(days=7)

                # You can pass an explicit 'livecrawl' param if needed:
                # e.g., livecrawl="always" to force Exa to re-fetch
                # But note it's slower
                search_response = self.exa.search_and_contents(
                    search_query,
                    text=True,
                    num_results=preferences.get("num_results", 2),
                    start_published_date=start_date.strftime("%Y-%m-%d"),
                    category='news',
                    # livecrawl="auto",   # or "always", "never"
                )

                summarized_articles = []
                for result in search_response.results:
                    if not result.text:
                        continue

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

                    summarized_articles.append({
                        "title": result.title,
                        "summary": summary_response.choices[0].message.content.strip(),
                        "source": result.url,
                        "date": getattr(result, 'published_date', None)
                    })

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
            "1. get_preferences\n2. fetch_and_summarize\n3. generate_news_script\n4. text_to_speech\n5. upload_audio\n",
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

            # ---------------------------------------------------------------------
            # 3) Parse script lines
            # ---------------------------------------------------------------------
            lines = script.split("\n")
            article_text_chunks = []
            for line in lines:
                clean = line.strip().lower()
                if clean and not clean.startswith("here are your news highlights") \
                and not clean.startswith("that's your update") \
                and not clean.startswith("that’s your update"):
                    article_text_chunks.append(line.strip())

            def word_count(s): 
                return len(s.split())

            total_words = sum(word_count(ch) for ch in article_text_chunks)

            # ---------------------------------------------------------------------
            # 4) Gather articles from self.state["summaries"]
            #    Each article is a dict: {title, summary, source}
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

            # Only handle as many articles as we have matching lines
            min_count = min(len(article_data), len(article_text_chunks))

            # ---------------------------------------------------------------------
            # 5) Inline image fetching
            # ---------------------------------------------------------------------
            def fetch_best_image_for(url):
                """Fetch an image for a given article URL using self.exa or HTML fallbacks."""
                best_image_url = None

                # (A) Use exa.get_contents if available
                try:
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
                                    break
                except Exception as e:
                    print(f"Exa content fetch failed for {url}: {e}")

                # (B) fallback: parse meta tags
                if not best_image_url:
                    try:
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
                                    break
                    except Exception as e:
                        print(f"Fallback meta parse failed: {e}")

                # (C) Attempt to download
                if best_image_url:
                    try:
                        r = requests.get(best_image_url, timeout=15)
                        if r.status_code == 200:
                            with BytesIO(r.content) as buf:
                                try:
                                    pil_img = Image.open(buf).convert("RGB")
                                    if pil_img.width < 10 or pil_img.height < 10:
                                        print("Too small image, skipping.")
                                        return None
                                    os.makedirs("temp_images", exist_ok=True)
                                    img_path = f"temp_images/img_{abs(hash(url))}.png"
                                    pil_img.save(img_path)
                                    return img_path
                                except UnidentifiedImageError:
                                    print("Unidentified image format.")
                                except Exception as e:
                                    print(f"Error processing image: {e}")
                    except Exception as e:
                        print(f"Could not download best_image_url: {e}")

                # (D) fallback: create a default
                try:
                    os.makedirs("temp_images", exist_ok=True)
                    default_path = f"temp_images/default_img_{abs(hash(url))}.png"
                    fallback_img = Image.new("RGB", (600, 338), color=(60,60,80))
                    fallback_img.save(default_path)
                    return default_path
                except Exception as e:
                    print(f"Could not create default image: {e}")

                # If all else fails:
                return None

            images_for_articles = []
            for art in article_data:
                path = fetch_best_image_for(art["url"])
                images_for_articles.append(path)

            # ---------------------------------------------------------------------
            # 6) Build base clips
            # ---------------------------------------------------------------------
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

            # Intro (2 seconds)
            intro_duration = 2
            intro_text = TextClip(
                "SonicPress News",
                fontsize=70,
                color="white",
                font="Arial-Bold",
                method="caption"
            ).set_position("center").set_duration(intro_duration)
            all_clips.append(intro_text)

            # Outro (last 3 seconds)
            outro_duration = 3
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

            # Ticker
            ticker_height = 60
            ticker_bg = ColorClip((width, ticker_height), color=(200, 50, 50)).set_duration(total_duration)
            ticker_y = height - ticker_height - 80
            ticker_bg = ticker_bg.set_position((0, ticker_y))
            all_clips.append(ticker_bg)

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

            # ---------------------------------------------------------------------
            # 7) Article segments
            # ---------------------------------------------------------------------
            elapsed = intro_duration
            for i in range(min_count):
                chunk = article_text_chunks[i]
                wc = word_count(chunk)
                fraction = wc / total_words if total_words else 0
                segment_duration = fraction * (total_duration - (intro_duration + outro_duration))
                if segment_duration < 1:
                    segment_duration = 1.0

                start_time = elapsed
                elapsed += segment_duration

                # Image first, behind text
                img_path = images_for_articles[i]
                if img_path and os.path.exists(img_path):
                    try:
                        img_clip = ImageClip(img_path)
                        # Force max 600×338
                        iw, ih = img_clip.size
                        scale = min(600/iw, 338/ih) if (iw>600 or ih>338) else 1
                        new_w, new_h = int(iw*scale), int(ih*scale)
                        img_clip = img_clip.resize((new_w, new_h))
                        img_clip = img_clip.set_position(("center", 120)) \
                                        .set_start(start_time) \
                                        .set_duration(segment_duration)
                        all_clips.append(img_clip)
                    except Exception as e:
                        print(f"Error with image {img_path}: {e}")

                # HEADLINE (on top)
                headline_clip = TextClip(
                    article_data[i]["title"],
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

                # SUMMARY
                summary_clip = TextClip(
                    article_data[i]["summary"],
                    fontsize=26,
                    color="white",
                    font="Arial",
                    method="caption",
                    size=(width - 150, None),
                    align="center"
                ).set_position(("center", 500)) \
                .set_start(start_time) \
                .set_duration(segment_duration)
                all_clips.append(summary_clip)

            # ---------------------------------------------------------------------
            # 8) Compose final
            # ---------------------------------------------------------------------
            final_clip = CompositeVideoClip(all_clips).set_audio(audio)

            # Make sure output folder exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

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

            # ---------------------------------------------------------------------
            # 9) Cleanup
            # ---------------------------------------------------------------------
            for path in images_for_articles:
                if path and os.path.exists(path):
                    try:
                        os.remove(path)
                    except:
                        pass

            return output_path

        except Exception as e:
            print(f"Failed to generate video: {e}")
            raise