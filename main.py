from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import google.generativeai as genai
import os
import tempfile
import logging
import shutil
import yt_dlp
import re
from datetime import datetime
from typing import Optional, Tuple
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from langdetect import detect

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class VideoRequest(BaseModel):
    url: str
    target_language: str

class TikTokProcessor:
    def __init__(self):
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key not found")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temp_dir = tempfile.mkdtemp()
        
    def validate_url(self, url: str) -> bool:
        """Проверка корректности URL TikTok"""
        if not url:
            return False
        patterns = [
            r'https?://(www\.)?tiktok\.com/.*',
            r'https?://vm\.tiktok\.com/\w+/?',
            r'https?://vt\.tiktok\.com/\w+/?'
        ]
        return any(bool(re.match(pattern, url)) for pattern in patterns)

    def get_safe_filename(self, filename: str, max_length: int = 50) -> str:
        """Создание безопасного имени файла"""
        name, ext = os.path.splitext(filename)
        name = re.sub(r'[^\w\s-]', '', name)
        name = re.sub(r'[-\s]+', '-', name).strip('-')
        if len(name) > max_length:
            name = name[:max_length]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"{name}_{timestamp}{ext}"

    def download_video(self, url: str) -> str:
        """Загрузка видео из TikTok"""
        if not self.validate_url(url):
            raise ValueError("Invalid TikTok URL format")

        try:
            video_opts = {
                'outtmpl': os.path.join(self.temp_dir, '%(id)s.%(ext)s'),
                'format': 'best',
                'noplaylist': True,
            }

            with yt_dlp.YoutubeDL(video_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_filename = ydl.prepare_filename(info)
                video_safe_filename = self.get_safe_filename(
                    f"tiktok_video_{os.path.basename(video_filename)}"
                )
                video_safe_path = os.path.join(self.temp_dir, video_safe_filename)
                if os.path.exists(video_filename):
                    os.rename(video_filename, video_safe_path)
                    return video_safe_path
                raise FileNotFoundError("Downloaded video file not found")
                
        except Exception as e:
            logger.error(f"Video download error: {str(e)}")
            raise

    def process_video(self, url: str, target_language: str) -> Tuple[str, str]:
        """Основной процесс обработки видео"""
        try:
            # Загрузка видео
            video_path = self.download_video(url)
            
            # Извлечение аудио
            audio_path = os.path.join(self.temp_dir, 'audio.mp3')
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, codec='mp3', verbose=False)
            video.close()
            
            # Транскрибация
            with open(audio_path, 'rb') as f:
                audio_data = f.read()

            # Получаем транскрипцию
            response = self.model.generate_content([
                "Transcribe this audio accurately, preserving all details and context.",
                {
                    "mime_type": "audio/mp3",
                    "data": audio_data
                }
            ])
            transcript = response.text
            
            # Генерируем саммари
            language_prompts = {
                'en': 'Generate a comprehensive summary in English:',
                'ru': 'Составьте подробное резюме на русском языке:',
                'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
            }
            
            prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {transcript}"
            summary_response = self.model.generate_content(prompt)
            summary = summary_response.text
            
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

# HTML шаблон (оставьте тот же HTML_TEMPLATE, что был раньше)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_TEMPLATE

@app.post("/process")
async def process_video(request: VideoRequest):
    processor = TikTokProcessor()
    try:
        transcript, summary = processor.process_video(request.url, request.target_language)
        return {
            "transcription": transcript,
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
