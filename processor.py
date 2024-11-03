import os
import tempfile
import logging
import shutil
import time
from typing import Tuple, Optional
from datetime import datetime
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip
from langdetect import detect
import re

logger = logging.getLogger(__name__)

class RetryStrategy:
    def __init__(self, max_attempts=3, delay=1):
        self.max_attempts = max_attempts
        self.delay = delay

    def execute(self, func, *args, **kwargs):
        last_exception = None
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}")
                if attempt < self.max_attempts - 1:
                    time.sleep(self.delay)
        raise last_exception

class TikTokProcessor:
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key not found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temp_dir = tempfile.mkdtemp()
        self.retry_strategy = RetryStrategy()

    def validate_url(self, url: str) -> bool:
        if not url:
            return False
        patterns = [
            r'https?://(www\.)?tiktok\.com/.*',
            r'https?://vm\.tiktok\.com/\w+/?',
            r'https?://vt\.tiktok\.com/\w+/?'
        ]
        return any(bool(re.match(pattern, url)) for pattern in patterns)

    def get_safe_filename(self, filename: str, max_length: int = 50) -> str:
        name, ext = os.path.splitext(filename)
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[-\s]+', '-', name).strip('-')
        if len(name) > max_length:
            name = name[:max_length]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}{ext}"

    def download_video(self, url: str) -> str:
        if not self.validate_url(url):
            raise ValueError("Invalid TikTok URL format")

        def _download():
            file_id = os.urandom(4).hex()
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(self.temp_dir, f'video_{file_id}.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'force_generic_extractor': False,
                'ignoreerrors': False,
                'nocheckcertificate': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Upgrade-Insecure-Requests': '1'
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filename = ydl.prepare_filename(info)
                
                if os.path.exists(filename):
                    return filename
                
                base, _ = os.path.splitext(filename)
                for ext in ['.mp4', '.webm', '.mkv']:
                    alt_filename = base + ext
                    if os.path.exists(alt_filename):
                        return alt_filename
                
                raise FileNotFoundError("Downloaded video file not found")

        return self.retry_strategy.execute(_download)

    def extract_audio(self, video_path: str) -> str:
        def _extract():
            audio_path = os.path.join(self.temp_dir, 'audio.mp3')
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, codec='mp3', verbose=False)
            video.close()
            return audio_path

        return self.retry_strategy.execute(_extract)

    def transcribe_audio(self, audio_path: str) -> str:
        def _transcribe():
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            response = self.model.generate_content([
                "Transcribe this audio accurately, preserving all details and context.",
                {
                    "mime_type": "audio/mp3",
                    "data": audio_data
                }
            ])
            return response.text

        return self.retry_strategy.execute(_transcribe)

    def generate_summary(self, text: str, target_language: str) -> str:
        def _summarize():
            language_prompts = {
                'en': 'Generate a comprehensive summary in English:',
                'ru': 'Составьте подробное резюме на русском языке:',
                'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
            }
            
            prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {text}"
            response = self.model.generate_content(prompt)
            return response.text

        return self.retry_strategy.execute(_summarize)

    def process_video(self, url: str, target_language: str) -> Tuple[str, str]:
        try:
            video_path = self.download_video(url)
            logger.info(f"Video downloaded: {video_path}")
            
            audio_path = self.extract_audio(video_path)
            logger.info(f"Audio extracted: {audio_path}")
            
            transcript = self.transcribe_audio(audio_path)
            logger.info("Transcription completed")
            
            summary = self.generate_summary(transcript, target_language)
            logger.info("Summary generated")
            
            return transcript, summary
            
        except Exception as e:
            logger.error(f"Processing error: {str(e)}")
            raise
        finally:
            try:
                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
                self.temp_dir = tempfile.mkdtemp()
            except Exception as e:
                logger.error(f"Cleanup error: {str(e)}")
