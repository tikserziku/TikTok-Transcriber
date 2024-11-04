import os
import tempfile
import logging
import shutil
import time
import asyncio
from typing import Tuple, Optional
from datetime import datetime
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip
import re
from .api_key_manager import APIKeyManager

# Настройка логирования
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
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_attempts - 1:
                    time.sleep(self.delay)
        if last_exception:
            raise last_exception

class TikTokProcessor:
    def __init__(self):
        self.api_key_manager = APIKeyManager()
        self.temp_dir = tempfile.mkdtemp()
        self.retry_strategy = RetryStrategy()
        self.extracted_audio_path = None
        self._init_gemini()

    def _init_gemini(self):
        """Инициализация Gemini с текущим API ключом"""
        api_key = self.api_key_manager.get_next_key()
        if not api_key:
            raise ValueError("No available API keys")
            
        genai.configure(api_key=api_key)
        self.current_api_key = api_key
        self.model = genai.GenerativeModel('gemini-1.5-pro')

    def cleanup(self):
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def validate_url(self, url: str) -> bool:
        if not url:
            return False
        patterns = [
            r'https?://(www\.)?tiktok\.com/.*',
            r'https?://vm\.tiktok\.com/\w+/?',
            r'https?://vt\.tiktok\.com/\w+/?'
        ]
        return any(bool(re.match(pattern, url)) for pattern in patterns)

    def download_video(self, url: str) -> str:
        if not self.validate_url(url):
            raise ValueError("Invalid TikTok URL format")

        def _download():
            file_id = os.urandom(4).hex()
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(self.temp_dir, f'video_{file_id}.%(ext)s'),
                'quiet': False,
                'no_warnings': False,
                'extract_flat': False,
                'force_generic_extractor': False,
                'ignoreerrors': False,
                'nocheckcertificate': True,
                'headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Upgrade-Insecure-Requests': '1',
                    'Referer': 'https://www.tiktok.com/'
                },
                'socket_timeout': 30,
                'retries': 10,
            }

            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    logger.info(f"Attempting to extract video info for URL: {url}")
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        raise ValueError("Could not extract video information")

                    logger.info("Video info extracted successfully, starting download")
                    ydl.download([url])

                    filename = ydl.prepare_filename(info)
                    logger.info(f"Prepared filename: {filename}")

                    if os.path.exists(filename):
                        logger.info(f"Video downloaded successfully: {filename}")
                        return filename

                    base, _ = os.path.splitext(filename)
                    for ext in ['.mp4', '.webm', '.mkv']:
                        alt_filename = base + ext
                        if os.path.exists(alt_filename):
                            logger.info(f"Found video with alternative extension: {alt_filename}")
                            return alt_filename

                    raise FileNotFoundError(f"Downloaded file not found: {filename}")

            except Exception as e:
                logger.error(f"Download error: {e}")
                raise

        return self.retry_strategy.execute(_download)

    def extract_audio(self, video_path: str) -> str:
        def _extract():
            timestamp = int(time.time())
            audio_path = os.path.join(self.temp_dir, f'audio_{timestamp}.mp3')
            try:
                video_size = os.path.getsize(video_path)
                logger.info(f"Video file size: {video_size / (1024*1024):.2f} MB")

                video = VideoFileClip(video_path)
                duration = video.duration
                logger.info(f"Video duration: {duration:.2f} seconds")
                
                video.audio.write_audiofile(
                    audio_path,
                    codec='mp3',
                    bitrate='128k',
                    verbose=False
                )
                video.close()

                self.extracted_audio_path = audio_path
                logger.info(f"Audio extracted successfully: {audio_path}")
                return audio_path

            except Exception as e:
                logger.error(f"Error extracting audio: {e}")
                if 'video' in locals():
                    video.close()
                raise

        return self.retry_strategy.execute(_extract)

    def get_extracted_audio_path(self) -> Optional[str]:
        return self.extracted_audio_path

    async def transcribe_audio(self, audio_path: str) -> Optional[str]:
        try:
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            response = await asyncio.to_thread(
                self.model.generate_content,
                [
                    "Transcribe this audio accurately, preserving all details and context.",
                    {
                        "mime_type": "audio/mp3",
                        "data": audio_data
                    }
                ]
            )
            return response.text
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            self.api_key_manager.mark_key_error(self.current_api_key, str(e))
            new_key = self.api_key_manager.get_next_key()
            if new_key:
                self.current_api_key = new_key
                genai.configure(api_key=new_key)
                self.model = genai.GenerativeModel('gemini-1.5-pro')
                return await self.transcribe_audio(audio_path)
            return None

    async def generate_summary(self, text: str, target_language: str) -> str:
        language_prompts = {
            'en': 'Generate a comprehensive summary in English:',
            'ru': 'Составьте подробное резюме на русском языке:',
            'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
        }

        prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {text}"
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content,
                prompt
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            self.api_key_manager.mark_key_error(self.current_api_key, str(e))
            new_key = self.api_key_manager.get_next_key()
            if new_key:
                self.current_api_key = new_key
                genai.configure(api_key=new_key)
                self.model = genai.GenerativeModel('gemini-1.5-pro')
                return await self.generate_summary(text, target_language)
            raise

    async def process_video(self, url: str, target_language: str) -> Tuple[str, str, Optional[str]]:
        """Process video and return transcript, summary and audio path"""
        try:
            video_path = self.download_video(url)
            logger.info(f"Video downloaded: {video_path}")

            audio_path = self.extract_audio(video_path)
            logger.info(f"Audio extracted: {audio_path}")

            transcript = await self.transcribe_audio(audio_path)
            if transcript is None:
                logger.warning("Transcription failed, but audio was extracted successfully")
                return "Transcription failed", "Summary not available", audio_path

            logger.info("Transcription completed")

            summary = await self.generate_summary(transcript, target_language)
            logger.info("Summary generated")

            return transcript, summary, audio_path

        except Exception as e:
            logger.error(f"Processing error: {e}")
            if self.extracted_audio_path and os.path.exists(self.extracted_audio_path):
                return "Processing failed", "Processing failed", self.extracted_audio_path
            raise
