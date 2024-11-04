import os
import tempfile
import logging
import shutil
import time
from typing import Tuple
from datetime import datetime
import yt_dlp
import google.generativeai as genai
from moviepy.editor import VideoFileClip
import re

logger = logging.getLogger(__name__)


class RetryStrategy:
    def __init__(self, max_attempts=3, delay=1, allowed_exceptions=None):
        self.max_attempts = max_attempts
        self.delay = delay
        self.allowed_exceptions = allowed_exceptions or (Exception,)

    def execute(self, func, *args, **kwargs):
        for attempt in range(self.max_attempts):
            try:
                return func(*args, **kwargs)
            except self.allowed_exceptions as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.max_attempts - 1:
                    time.sleep(self.delay)
                else:
                    raise


class TikTokProcessor:
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key not found")

        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temp_dir_obj = tempfile.TemporaryDirectory()
        self.temp_dir = self.temp_dir_obj.name
        self.retry_strategy = RetryStrategy(
            allowed_exceptions=(
                Exception,
                yt_dlp.utils.DownloadError,
                genai.errors.ResourceExhaustedError,
            )
        )

    def __del__(self):
        try:
            self.temp_dir_obj.cleanup()
        except Exception as e:
            logger.error(f"Error cleaning up temporary directory: {e}")

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
        name = re.sub(r'[^\w\s-]', '', name).strip()
        name = re.sub(r'[-\s]+', '-', name).strip('-_')
        name = name.lower()
        if len(name) > max_length:
            name = name[:max_length]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}{ext}"

    def download_video(self, url: str) -> str:
        if not self.validate_url(url):
            raise ValueError("Invalid TikTok URL format")

        def _download():
            ydl_opts = {
                'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                'outtmpl': os.path.join(self.temp_dir, '%(title)s-%(id)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True,
            }
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    if 'requested_downloads' in info:
                        file_info = info['requested_downloads'][0]
                        return file_info['filepath']
                    else:
                        raise ValueError("No video file info found after download.")
            except Exception as e:
                logger.error(f"Error during video download with yt-dlp: {e}")
                raise

        return self.retry_strategy.execute(_download)

    def extract_audio(self, video_path: str) -> str:
        def _extract():
            audio_path = os.path.join(self.temp_dir, 'audio.mp3')
            try:
                video = VideoFileClip(video_path)
                video.audio.write_audiofile(audio_path, codec='mp3', verbose=False)
                video.close()
                return audio_path
            except Exception as e:
                logger.error(f"Error extracting audio: {e}")
                raise

        return self.retry_strategy.execute(_extract)

    def transcribe_audio(self, audio_path: str) -> str:
        def _transcribe():
            try:
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
            except genai.errors.ResourceExhaustedError as e:
                if hasattr(e, "retry_after"):
                    retry_after = e.retry_after.seconds
                else:
                    retry_after = 60
                logger.warning(f"Google API rate limit reached. Retrying after {retry_after} seconds...")
                time.sleep(retry_after)
                return _transcribe()
            except Exception as e:
                logger.error(f"Error during transcription: {e}")
                raise

        return self.retry_strategy.execute(_transcribe)

    def generate_summary(self, text: str, target_language: str) -> str:
        def _summarize():
            language_prompts = {
                'en': 'Generate a comprehensive summary in English:',
                'ru': 'Составьте подробное резюме на русском языке:',
                'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
            }

            prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {text}"
            try:
                response = self.model.generate_content(prompt)
                return response.text
            except Exception as e:
                logger.error(f"Error generating summary: {e}")
                raise

        return self.retry_strategy.execute(_summarize)

    def process_video(self, url: str, target_language: str) -> Tuple[str, str, str]:
        try:
            video_path = self.download_video(url)
            logger.info(f"Video downloaded: {video_path}")

            audio_path = self.extract_audio(video_path)
            logger.info(f"Audio extracted: {audio_path}")

            transcript = self.transcribe_audio(audio_path)
            logger.info("Transcription completed")

            summary = self.generate_summary(transcript, target_language)
            logger.info("Summary generated")

            return transcript, summary, audio_path

        except Exception as e:
            logger.error(f"Processing error: {e}")
            raise
