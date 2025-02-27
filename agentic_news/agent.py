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
        """
        Generate a news video using the script, images, and audio narration.
        This version addresses:
        - A scrolling ticker that is clearly visible (not hidden by controls).
        - Article-image timing synced to script by word-count ratio.
        - Fallback if no image is found.
        """
        from moviepy.editor import (
            ColorClip, TextClip, AudioFileClip,
            CompositeVideoClip, ImageClip
        )
        from PIL import Image, UnidentifiedImageError
        import os
        import re
        import requests
        from io import BytesIO
        from urllib.parse import urlparse

        try:
            # ---------------------------------------------------------------------
            # 1. PREPARE AUDIO/BACKGROUND
            # ---------------------------------------------------------------------
            audio = AudioFileClip(audio_path)
            total_duration = audio.duration
            
            width, height = 1280, 720
            background = ColorClip((width, height), color=(0, 20, 40))
            background = background.set_duration(total_duration)
            
            # ---------------------------------------------------------------------
            # 2. PARSE SCRIPT PER ARTICLE
            #    - We assume your final script has a structure like:
            #         "Here are your news highlights.\n(Article 1) ... \n(Article 2) ...\nThat's your update."
            #    - We'll try to identify each article chunk by splitting lines that
            #      contain the article summaries. Adjust splitting logic if needed.
            # ---------------------------------------------------------------------
            # Example naive approach: split by double-newline or some marker
            # If your script doesn't have consistent newlines, you can adapt.
            article_text_chunks = []
            lines = script.split("\n")
            
            # Gather each line that contains a summary or mention. In your code,
            # you might have "Summary: ..." or something else. Adapt to your format.
            # For simplicity, we treat every separate line as a "chunk" if it
            # belongs to an article, ignoring intro/outro lines.
            
            # We'll assume the final script has, say, N lines that each correspond
            # to one summarized story. This is just an example. Adapt to your real format.
            for line in lines:
                line_clean = line.strip()
                if len(line_clean) > 0 and not line_clean.lower().startswith("here are your news highlights") \
                and not line_clean.lower().startswith("that's your update") \
                and not line_clean.lower().startswith("that's your update"):
                    article_text_chunks.append(line_clean)
            
            # Count total words in *all* article lines
            def word_count(s): return len(s.split())
            total_words = sum(word_count(ch) for ch in article_text_chunks)
            
            # ---------------------------------------------------------------------
            # 3. GATHER ARTICLES AND IMAGES
            #    We'll reuse self.state['summaries'] which you have after fetch_and_summarize.
            #    They're presumably in the same order you used for script generation.
            #    If they're not in the exact same order, adapt accordingly.
            # ---------------------------------------------------------------------
            summaries = self.state.get('summaries', [])
            
            # Flatten out: [ (title, summary, source) ... ] in the same order
            article_data = []
            for category in summaries:
                for art in category['articles']:
                    article_data.append({
                        'title': art['title'],
                        'summary': art['summary'],
                        'url': art['source'],
                    })
            
            # If you have more text lines than articles or vice versa, handle that
            # here. We'll match them up by index in order.
            min_count = min(len(article_data), len(article_text_chunks))
            
            # Pull images from Exa or fallback
            # We'll store (img_path or None) in a parallel list.
            def fetch_best_image_for(url):
                """Try to find the best image for a given article URL using Exa or fallback."""
                best_image_url = None
                
                # 1) Use self.exa get_contents if available
                #    We can do a single call outside the loop for all URLs,
                #    but for brevity we do it per-article.
                try:
                    print(f"Fetching content for URL: {url}")
                    # Use only the basic parameters that are supported
                    content_response = self.exa.get_contents(urls=[url])
                    if content_response and hasattr(content_response, 'contents') and content_response.contents:
                        for c in content_response.contents:
                            if hasattr(c, 'images') and c.images:
                                print(f"Found {len(c.images)} images in content")
                                valid_imgs = [
                                    img for img in c.images
                                    if hasattr(img, 'width') and hasattr(img, 'height') and 
                                    img.width >= 300 and img.height >= 200
                                ]
                                if valid_imgs:
                                    best_image = max(valid_imgs, key=lambda x: x.width * x.height)
                                    best_image_url = best_image.url
                                    print(f"Selected best image: {best_image_url}")
                                    break
                except Exception as e:
                    print(f"Exa content fetch failed for {url}: {e}")
                
                # 2) Fallback: Try multiple meta tag patterns for images
                if not best_image_url:
                    try:
                        print(f"Trying fallback image extraction for {url}")
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        resp = requests.get(url, headers=headers, timeout=10)
                        if resp.status_code == 200:
                            # Try multiple meta tag patterns
                            meta_patterns = [
                                r'<meta\s+(?:property|name)="(?:og:image|og:image:secure_url)"\s+content="([^"]+)"',
                                r'<meta\s+(?:content)="([^"]+)"\s+(?:property|name)="(?:og:image|og:image:secure_url)"',
                                r'<meta\s+(?:property|name)="(?:twitter:image)"\s+content="([^"]+)"',
                                r'<meta\s+(?:content)="([^"]+)"\s+(?:property|name)="(?:twitter:image)"',
                                r'<img[^>]+class="[^"]*(?:featured|hero|main|article)[^"]*"[^>]+src="([^"]+)"',
                                r'<img[^>]+src="([^"]+(?:jpg|jpeg|png|gif))"[^>]+(?:width|height)="[2-9]\d{2,}"'
                            ]
                            
                            for pattern in meta_patterns:
                                matches = re.findall(pattern, resp.text)
                                if matches:
                                    best_image_url = matches[0]
                                    print(f"Found image via pattern: {best_image_url}")
                                    # Make relative URLs absolute
                                    if best_image_url.startswith('/'):
                                        parsed_url = urlparse(url)
                                        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                                        best_image_url = base_url + best_image_url
                                    break
                    except Exception as e:
                        print(f"Fallback meta-image fetch failed for {url}: {e}")
                
                # 3) Download & validate image
                if best_image_url:
                    try:
                        print(f"Downloading image from: {best_image_url}")
                        img_resp = requests.get(best_image_url, timeout=15)
                        if img_resp.status_code == 200:
                            with BytesIO(img_resp.content) as buf:
                                try:
                                    pil_img = Image.open(buf).convert("RGB")
                                    if pil_img.width < 10 or pil_img.height < 10:
                                        print(f"Image too small: {pil_img.width}x{pil_img.height}")
                                        return None
                                    
                                    # Create output directory if it doesn't exist
                                    os.makedirs("temp_images", exist_ok=True)
                                    
                                    # Resize keeping aspect ratio
                                    try:
                                        pil_img.thumbnail((800, 800), Image.LANCZOS)
                                    except AttributeError:
                                        # Fallback for older PIL versions
                                        pil_img.thumbnail((800, 800), Image.ANTIALIAS)
                                    
                                    temp_img_path = f"temp_images/temp_img_{abs(hash(url))}.png"
                                    pil_img.save(temp_img_path)
                                    print(f"Successfully saved image to {temp_img_path}")
                                    return temp_img_path
                                except UnidentifiedImageError:
                                    print(f"Could not identify image format for {best_image_url}")
                                except Exception as e:
                                    print(f"Error processing image from {best_image_url}: {e}")
                    except Exception as e:
                        print(f"Could not retrieve/validate {best_image_url}: {e}")
                
                # 4) Last resort: Create a default image with the article title
                try:
                    print(f"Creating default image for {url}")
                    # Get the article title from article_data
                    article_title = None
                    for article in article_data:
                        if article['url'] == url:
                            article_title = article['title']
                            break
                    
                    if not article_title:
                        article_title = "News Article"
                    
                    # Create a simple image with the title
                    img_width, img_height = 800, 450
                    background_color = (60, 60, 100)
                    
                    # Create a blank image with background color
                    img = Image.new('RGB', (img_width, img_height), background_color)
                    
                    # Create output directory if it doesn't exist
                    os.makedirs("temp_images", exist_ok=True)
                    
                    # Save the image
                    temp_img_path = f"temp_images/default_img_{abs(hash(url))}.png"
                    img.save(temp_img_path)
                    print(f"Created default image at {temp_img_path}")
                    return temp_img_path
                except Exception as e:
                    print(f"Failed to create default image: {e}")
                
                print(f"No valid image found for {url}")
                return None
            
            images_for_articles = []
            for idx, article in enumerate(article_data):
                img_path = fetch_best_image_for(article['url'])
                images_for_articles.append(img_path)
            
            # ---------------------------------------------------------------------
            # 4. BUILD CLIPS
            # ---------------------------------------------------------------------
            all_clips = [background]
            
            # Branding / Logo text
            logo_text = TextClip(
                "SonicPress",
                fontsize=40,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position((50, 50)).set_duration(total_duration)
            all_clips.append(logo_text)
            
            # Intro
            intro_duration = 2  # first 2s
            intro_text = TextClip(
                "SonicPress News",
                fontsize=70,
                color='white',
                font='Arial-Bold',
                method='caption'
            ).set_position('center').set_duration(intro_duration)
            all_clips.append(intro_text)
            
            # Outro
            outro_duration = 3  # last 3s
            outro_text = TextClip(
                "Thanks for watching!",
                fontsize=50,
                color='white',
                font='Arial-Bold',
                method='label'
            ).set_position('center').set_start(total_duration - outro_duration).set_duration(outro_duration)
            all_clips.append(outro_text)
            
            # 4A. Make a SCROLLING TICKER along the bottom
            #     We'll place it above the potential play controls. For instance, at y = height-100.
            ticker_height = 60
            ticker_bg = ColorClip(size=(width, ticker_height), color=(200, 50, 50)).set_duration(total_duration)
            # shift ticker up a bit from bottom
            ticker_y = height - ticker_height - 40
            
            ticker_bg = ticker_bg.set_position((0, ticker_y))
            all_clips.append(ticker_bg)
            
            # Ticker text content
            ticker_titles = [art['title'] for art in article_data]
            ticker_text_content = " • ".join(ticker_titles)
            
            # Ticker as a horizontally-moving clip
            # We'll create an off-screen starting position, move left over total_duration
            text_clip = TextClip(
                ticker_text_content,
                fontsize=28,
                color='white',
                font='Arial-Bold'
            )
            
            text_clip_w, _ = text_clip.size
            # Start at x=width, end at x= -text_clip_w, over total_duration
            # We define a dynamic position function:
            def scroll_position(t):
                # linear interpolation from width to -(text_clip_w) over total_duration
                x = width - (width + text_clip_w) * (t / total_duration)
                return (x, ticker_y + (ticker_height - text_clip.h) // 2)
            
            scrolling_ticker = text_clip.set_duration(total_duration).set_position(scroll_position)
            all_clips.append(scrolling_ticker)
            
            # 4B. Generate article segments in sync with audio (word-count ratio).
            #     For article i, we compute its portion of the total script words.
            # ---------------------------------------------------------------------
            elapsed = intro_duration  # start placing first article after intro
            for i in range(min_count):
                article_text = article_text_chunks[i]
                article_wordcount = word_count(article_text)
                # fraction of total script
                fraction = article_wordcount / total_words if total_words else 0
                # how many seconds this article consumes in the narration
                segment_duration = fraction * (total_duration - (intro_duration + outro_duration))
                if segment_duration < 1:
                    segment_duration = 1.0  # ensure at least 1s
                
                start_time = elapsed
                end_time = start_time + segment_duration
                
                # HEADLINE
                headline_clip = TextClip(
                    article_data[i]['title'],
                    fontsize=34,
                    color='white',
                    font='Arial-Bold',
                    method='caption',
                    size=(width - 100, None),
                    align='center'
                ).set_position(('center', 100)) \
                .set_start(start_time) \
                .set_duration(segment_duration)
                all_clips.append(headline_clip)
                
                # SUMMARY
                summary_clip = TextClip(
                    article_data[i]['summary'],
                    fontsize=28,
                    color='white',
                    font='Arial',
                    method='caption',
                    size=(width - 200, None),
                    align='center'
                ).set_position(('center', 600)) \
                .set_start(start_time) \
                .set_duration(segment_duration)
                all_clips.append(summary_clip)
                
                # IMAGE or FALLBACK BACKGROUND
                if images_for_articles[i] is not None:
                    # show the downloaded image
                    img_clip = ImageClip(images_for_articles[i])
                    # center image at y=200 for instance
                    img_clip = img_clip.set_position(('center', 180)) \
                                    .set_start(start_time) \
                                    .set_duration(segment_duration)
                    all_clips.append(img_clip)
                else:
                    # fallback color block
                    fallback_bg = ColorClip(size=(800, 400), color=(60, 60, 60)) \
                        .set_position(('center', 180)) \
                        .set_start(start_time) \
                        .set_duration(segment_duration)
                    no_image_text = TextClip(
                        "No image available",
                        fontsize=26,
                        color='white',
                        font='Arial-Bold'
                    ).set_position(('center', 360)) \
                    .set_start(start_time) \
                    .set_duration(segment_duration)
                    all_clips.extend([fallback_bg, no_image_text])
                
                # Advance time pointer
                elapsed += segment_duration
            
            # ---------------------------------------------------------------------
            # 5. COMBINE & RENDER
            # ---------------------------------------------------------------------
            final_clip = CompositeVideoClip(all_clips).set_audio(audio)
            
            final_clip.write_videofile(
                output_path,
                fps=24,
                codec='libx264',
                audio_codec='aac',
                threads=4,
                preset='medium',
                bitrate='3000k'
            )
            
            # Cleanup
            final_clip.close()
            audio.close()
            
            # Remove temp images
            for img_path in images_for_articles:
                if img_path and os.path.exists(img_path):
                    try:
                        os.remove(img_path)
                    except Exception as e:
                        print(f"Failed to remove temp image {img_path}: {e}")
            
            # Try to remove the temp directory if it's empty
            try:
                if os.path.exists("temp_images") and not os.listdir("temp_images"):
                    os.rmdir("temp_images")
            except Exception as e:
                print(f"Failed to remove temp_images directory: {e}")
            
            return output_path
        
        except Exception as e:
            print(f"Failed to generate video: {str(e)}")
            raise
