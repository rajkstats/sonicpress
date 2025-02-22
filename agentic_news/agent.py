import io
import os
import json
import requests
from datetime import datetime, timedelta
from google.cloud import storage
from pydub import AudioSegment
from exa_py import Exa
from litellm import completion as chat_completion

from .config import (
    EXA_API_KEY,
    ELEVENLABS_API_KEY,
    ELEVENLABS_BASE_URL,
    GCS_BUCKET_NAME,
    FUNCTION_DEFINITIONS as functions_definitions
)
from .providers import LiteLLMProvider, Message
from .utils.logger import Logger

class NewsAgent:
    def __init__(self, save_logs=True):
        self.messages = []  # Agent memory
        self.state = {}

        # Initialize Exa client
        self.exa = Exa(EXA_API_KEY)
        
        # Set up logging if enabled
        if save_logs:
            logger.log_file = "news_agent_log.html"

    def get_preferences(self):
        """
        Tool: Preferences Retriever (Firestore)
        Simulate retrieving user preferences.
        Returns:
            dict: User preferences including categories, preferredSources, tts_voice, and date.
        """
        preferences = {
            "categories": ["Tech and Innovation"],
            "voice_id":'9BWtsMINqrJLrRacOk9x' ,
            "date": "2023-10-01",
        }
        print("Retrieved Preferences:", preferences)
        return preferences

    def fetch_and_summarize(self,preferences, model="mistral/mistral-small-latest"):
        """Fetch and summarize news articles in one pass."""
        try:
            if isinstance(preferences, str):
                preferences = json.loads(preferences)
                
            search_results = []
            
            for category in preferences["categories"]:
                query_response = chat_completion(
                    messages=[
                        {"role": "system", "content": "Generate a search query in English only. Respond with ONLY the query text."},
                        {"role": "user", "content": f"Latest news about: {category}"}
                    ],
                    model=model,
                    temperature=0.7
                )
                
                search_query = query_response.choices[0].message.content.strip()
                print(f"\nSearching for: {search_query}")
                
                search_response = self.exa.search_and_contents(
                    search_query,
                    text=True,
                    num_results=preferences.get("num_results", 2),
                    start_published_date=(datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
                    category='news'
                )
                
                summarized_articles = []
                for result in search_response.results:
                    if not result.text:
                        continue
                        
                    summary_response = chat_completion(
                        messages=[{
                            "role": "system", 
                            "content": """You are a news summarizer. Create a single-sentence news summary that:
                                              - Uses exactly 20-30 words
                                              - No markdown, bullets, or special formatting
                                              - Simple present tense
                                              - Focus on the single most important fact
                                              - Must be in plain text format
                                              - Must be in English"""
                        }, {
                            "role": "user",
                            "content": result.text
                        }],
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
                        
            return search_results
            
        except Exception as e:
            print(f"Error fetching and summarizing news: {str(e)}")
            return []

    def generate_news_script(self,summarized_results, preferences, model="mistral/mistral-small-latest", temperature=0.7):
        """Generate an adaptive news script based on content volume."""
        try:
            prefs_str = ", ".join(preferences["categories"])
            total_articles = sum(len(cat['articles']) for cat in summarized_results)
            
            system_message = (
                "You are a professional news anchor. Create a natural, conversational news brief.\n"
                "Format:\n"
                "1. Start: 'Here are your news highlights'\n"
                "2. Body: One clear sentence per news item. Integrate sources naturally.\n"
                "Example: 'According to NASA, the Mars rover has discovered new signs of water'\n"
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
        """
        Convert text to speech using ElevenLabs API with advanced voice settings.
        
        Args:
            text (str): The text to convert to speech
            voice_id (str): The voice model identifier
            model_id (str): The model to use for synthesis
            stability (float): Voice stability (0-1)
            similarity_boost (float): Voice clarity and similarity to original (0-1)
            style (float): Speaking style parameter (0-1)
            speed (float): Speech rate multiplier (0.5-2.0)
            output_format (str): Audio output format
        """
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
        
        # Adjust text for speed modification if needed
        if speed != 1.0:
            # Add SSML tags for speed adjustment
            text = f'<speak><prosody rate="{int((speed-1)*100)}%">{text}</prosody></speak>'
            data["text"] = text

        response = requests.post(url, json=data, headers=headers)

        if response.status_code == 200:
            return response.content
        else:
            raise Exception(f"API Error {response.status_code}: {response.text}")

    def text_to_speech(self, user_text: str, voice_id: str, model_id: str = "eleven_multilingual_v2") -> str:
        """
        Generate speech from text using ElevenLabs API.
        Args:
            user_text (str): The input text to be synthesized
            voice_id (str): The voice model identifier
            model_id (str): The model to use for synthesis
        Returns:
            str: The file path to the generated audio file
        """
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
        """
        Tool: Storage/Uploader (Google Cloud Storage)
        Upload the audio file to GCS bucket and return a URL.
        Parameters:
            audio_file_path (str): Local path to the audio file.
        Returns:
            str: GCS URL where the audio file is stored.
        """
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
        func_impl = getattr(self, name.lower())
        if func_impl:
            try:
                if arguments and 'noop' in arguments:
                    arguments = {}
                
                processed_args = {}
                for key, value in arguments.items():
                    if isinstance(value, str):
                        try:
                            processed_args[key] = json.loads(value)
                        except json.JSONDecodeError:
                            processed_args[key] = value
                    else:
                        processed_args[key] = value
                
                # Handle different function cases
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
                
                # For other functions
                return func_impl(**processed_args) if processed_args else func_impl()
                
            except Exception as e:
                print(f"Error executing function: {str(e)}")
                return None
        else:
            return "Function not implemented."

    def run(self, instruction):
        self.messages.append(Message(f"OBJECTIVE: {instruction}"))
        
        system_message = Message(
            "You are a news assistant that must complete these steps in order:\n"
            "1. Get preferences using get_preferences\n"
            "2. Fetch and summarize news using fetch_and_summarize\n"
            "3. Generate a news script using generate_news_script\n"
            "4. Convert the script to speech using text_to_speech\n"
            "5. Upload the audio file using upload_audio\n"
            "Complete each step and use the results from previous steps as input to the next.",
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

        if content:
            print(f"\nTHOUGHT: {content}")  # Print initial thought
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
            
            content, next_tool_calls = action_model.call(
                [
                    system_message,
                    *self.messages,
                    Message("What's the next step we should take?")
                ],
                functions_definitions
            )
            
            if content:
                print(f"\nTHOUGHT: {content}")  # Print subsequent thoughts
                self.messages.append(Message(logger.log(f"THOUGHT: {content}", "blue")))
            
            if next_tool_calls:
                tool_calls.extend(next_tool_calls)

        return self.state.get("upload_audio")

logger = Logger()
action_model = LiteLLMProvider("large") 