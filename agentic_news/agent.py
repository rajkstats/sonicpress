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

    def generate_video(self, script: str, audio_path: str,
                       output_path: str = "output/news_video.mp4") -> str:
        """Generate a news video using the script, images, and audio narration."""
        try:
            audio = AudioFileClip(audio_path)
            duration = audio.duration

            width, height = 1280, 720
            background = ColorClip((width, height), color=(0, 20, 40))
            background = background.set_duration(duration)

            # Pull article data from self.state if it's stored after fetch_and_summarize
            summaries = self.state.get('summaries', [])

            # We'll gather images for each article
            image_clips = []
            article_data = []

            for category in summaries:
                for article in category['articles']:
                    if '/category/' in article['source'] or article['source'].endswith('/news'):
                        print(f"Skipping category page: {article['source']}")
                        continue
                    article_data.append({
                        'url': article['source'],
                        'summary': article['summary'],
                        'title': article['title']
                    })

            # Use Exa's contents endpoint to get images for all articles at once
            url_to_content = {}
            if article_data:
                article_urls = [article['url'] for article in article_data]
                try:
                    content_response = self.exa.get_contents(
                        urls=article_urls,
                        text=True,
                        extras={"imageLinks": 3}
                    )
                    
                    if content_response and hasattr(content_response, 'results'):
                        for result in content_response.results:
                            if hasattr(result, 'url'):
                                url_to_content[result.url] = result
                    
                    print(f"Retrieved content for {len(url_to_content)} URLs from Exa")
                except Exception as e:
                    print(f"Exa contents API error: {str(e)}")

            for idx, article in enumerate(article_data):
                best_image_url = None
                
                # Try to get image from Exa content first
                if article['url'] in url_to_content:
                    result = url_to_content[article['url']]
                    if hasattr(result, 'image') and result.image:
                        best_image_url = result.image
                    elif hasattr(result, 'extras') and hasattr(result.extras, 'imageLinks') and result.extras.imageLinks:
                        best_image_url = result.extras.imageLinks[0]
                
                # Fallback to the original method if needed
                if not best_image_url:
                    try:
                        # Original method as fallback
                        content_response = self.exa.get_contents(
                            urls=[article['url']],
                            max_image_count=3
                        )
                        if content_response and getattr(content_response, 'contents', []):
                            for content in content_response.contents:
                                if hasattr(content, 'images') and content.images:
                                    valid_imgs = [
                                        img for img in content.images
                                        if img.width >= 300 and img.height >= 200
                                    ]
                                    if valid_imgs:
                                        # Pick the largest
                                        best_image = max(valid_imgs, key=lambda x: x.width * x.height)
                                        best_image_url = best_image.url
                                        break
                    except Exception as e:
                        print(f"Exa get_contents fallback error for {article['url']}: {e}")

                # 2) Fallback: fetch HTML & look for <meta property="og:image">
                if not best_image_url:
                    try:
                        resp = requests.get(article['url'], timeout=10)
                        if resp.status_code == 200:
                            matches = re.findall(
                                r'<meta\s+(?:property|name)="(?:og:image|og:image:secure_url|twitter:image)"\s+content="([^"]+)"',
                                resp.text
                            )
                            if matches:
                                best_image_url = matches[0]
                                
                            # Make relative URLs absolute
                            if best_image_url and best_image_url.startswith('/'):
                                parsed_url = urlparse(article['url'])
                                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                                best_image_url = base_url + best_image_url
                    except Exception as e:
                        print(f"Fallback image fetch failed: {e}")

                # 3) Download & Validate image
                if best_image_url:
                    try:
                        img_response = requests.get(best_image_url, timeout=15)
                        img_response.raise_for_status()
                        with BytesIO(img_response.content) as buf:
                            pil_img = Image.open(buf).convert("RGB")

                        # Validate image dimensions
                        if pil_img.width <= 0 or pil_img.height <= 0:
                            print(f"Invalid image dimensions: {pil_img.width}x{pil_img.height}, skipping")
                            best_image_url = None
                            continue

                        # Resize while keeping aspect ratio - use Resampling.LANCZOS if available
                        try:
                            pil_img.thumbnail((800, 800), Resampling.LANCZOS)
                        except (ImportError, AttributeError):
                            # Fallback for older PIL versions
                            pil_img.thumbnail((800, 800))
                            
                        temp_img_path = f"temp_img_{idx}.png"
                        pil_img.save(temp_img_path)

                        segment_duration = duration / (len(article_data) + 1)
                        start_time = 2 + (idx * segment_duration)

                        # ImageClip
                        img_clip = ImageClip(temp_img_path)
                        img_clip = img_clip.set_position(('center', 180)) \
                                           .set_start(start_time) \
                                           .set_duration(segment_duration)

                        # Headline
                        headline_text = article['title'][:80]
                        if len(article['title']) > 80:
                            headline_text += '...'

                        headline = TextClip(
                            headline_text,
                            fontsize=28,
                            color='white',
                            font='Arial-Bold',
                            method='caption',
                            align='center',
                            size=(width - 100, None)
                        ).set_position(('center', 120)) \
                         .set_start(start_time) \
                         .set_duration(segment_duration)

                        # Caption
                        caption = TextClip(
                            article['summary'],
                            fontsize=24,
                            color='white',
                            font='Arial',
                            method='caption',
                            align='center',
                            size=(width - 200, None)
                        ).set_position(('center', 600)) \
                         .set_start(start_time) \
                         .set_duration(segment_duration)

                        image_clips.extend([img_clip, headline, caption])

                        print(f"Found image for {article['url']}: {best_image_url}")

                    except (requests.HTTPError, UnidentifiedImageError) as e:
                        print(f"Invalid or missing image for {article['url']}: {e}")
                else:
                    print(f"No valid image found for {article['url']}")

            # Branding elements
            logo_text = TextClip(
                "SonicPress",
                fontsize=30,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position((50, 50)).set_duration(duration)

            ticker_bg = ColorClip((width, 60), color=(200, 50, 50)).set_opacity(0.8)
            ticker_bg = ticker_bg.set_position(('center', height - 30)).set_duration(duration)

            # Construct a ticker text from article titles
            ticker_titles = [a['title'] for a in article_data]
            ticker_text_content = "BREAKING NEWS   •   " + "   •   ".join(ticker_titles)
            ticker_text = TextClip(
                ticker_text_content,
                fontsize=20,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position(('center', height - 30)).set_duration(duration)

            intro_text = TextClip(
                "SonicPress News",
                fontsize=70,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position('center').set_start(0).set_duration(2)

            outro_text = TextClip(
                "Thanks for watching",
                fontsize=50,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position('center').set_start(duration - 2).set_duration(2)

            all_clips = [background, logo_text, ticker_bg, ticker_text, intro_text, outro_text]
            all_clips.extend(image_clips)

            final_video = CompositeVideoClip(all_clips)
            final_video = final_video.set_audio(audio)

            final_video.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                threads=4,
                preset='medium',
                bitrate='3000k'
            )

            final_video.close()
            audio.close()

            # Cleanup temp images
            for idx in range(len(article_data)):
                temp_path = f"temp_img_{idx}.png"
                if os.path.exists(temp_path):
                    os.remove(temp_path)

            return output_path
        except Exception as e:
            print(f"Failed to generate video: {str(e)}")
            raise