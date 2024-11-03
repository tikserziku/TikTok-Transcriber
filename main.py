import os
import sys
import tempfile
import logging
import shutil
import re
from datetime import datetime
from typing import Optional, Tuple
from pathlib import Path

import yt_dlp
import google.generativeai as genai
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
from langdetect import detect

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# HTML шаблон
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TikTok Transcriber</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { padding: 20px; }
        .result-box {
            min-height: 200px;
            margin: 10px 0;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            position: relative;
        }
        .copy-btn {
            position: absolute;
            top: 10px;
            right: 10px;
        }
        .spinner {
            display: none;
            width: 50px;
            height: 50px;
            margin: 20px auto;
            border: 3px solid #f3f3f3;
            border-top: 3px solid #3498db;
            border-radius: 50%;
            animation: spin 1s linear infinite;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">📱 TikTok Transcriber</h1>
        
        <div class="row mb-3">
            <div class="col">
                <input type="text" id="tiktokUrl" class="form-control" 
                    placeholder="Вставьте ссылку на TikTok видео (например: https://vm.tiktok.com/...)">
            </div>
        </div>
        
        <div class="row mb-3">
            <div class="col-md-4">
                <select id="language" class="form-select">
                    <option value="en">English</option>
                    <option value="ru">Русский</option>
                    <option value="lt">Lietuvių</option>
                </select>
            </div>
            <div class="col-md-2">
                <button onclick="processVideo()" class="btn btn-primary w-100">Обработать</button>
            </div>
        </div>

        <div id="spinner" class="spinner"></div>
        
        <div class="row">
            <div class="col-md-6">
                <h3>Transcription</h3>
                <div id="transcription" class="result-box">
                    <button onclick="copyText('transcription')" class="btn btn-sm btn-secondary copy-btn">
                        Copy
                    </button>
                    <div class="content"></div>
                </div>
            </div>
            <div class="col-md-6">
                <h3>Summary</h3>
                <div id="summary" class="result-box">
                    <button onclick="copyText('summary')" class="btn btn-sm btn-secondary copy-btn">
                        Copy
                    </button>
                    <div class="content"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function processVideo() {
            const url = document.getElementById('tiktokUrl').value;
            const lang = document.getElementById('language').value;
            
            if (!url) {
                alert('Please enter TikTok URL');
                return;
            }

            // Показываем спиннер
            document.getElementById('spinner').style.display = 'block';
            
            // Очищаем предыдущие результаты
            document.getElementById('transcription').querySelector('.content').innerText = 'Processing...';
            document.getElementById('summary').querySelector('.content').innerText = 'Processing...';
            
            try {
                const response = await fetch('/process', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        target_language: lang
                    })
                });
                
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                
                const data = await response.json();
                
                document.getElementById('transcription').querySelector('.content').innerText = 
                    data.transcription || 'Transcription failed';
                document.getElementById('summary').querySelector('.content').innerText = 
                    data.summary || 'Summary failed';
            } catch (error) {
                alert('Error processing video: ' + error.message);
                document.getElementById('transcription').querySelector('.content').innerText = 'Error occurred';
                document.getElementById('summary').querySelector('.content').innerText = 'Error occurred';
            } finally {
                // Скрываем спиннер
                document.getElementById('spinner').style.display = 'none';
            }
        }
        
        function copyText(elementId) {
            const text = document.getElementById(elementId).querySelector('.content').innerText;
            navigator.clipboard.writeText(text);
            
            // Показываем уведомление о копировании
            const btn = document.getElementById(elementId).querySelector('.copy-btn');
            const originalText = btn.innerText;
            btn.innerText = 'Copied!';
            setTimeout(() => {
                btn.innerText = originalText;
            }, 2000);
        }
    </script>
</body>
</html>
"""
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
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Upgrade-Insecure-Requests': '1',
                'Cookie': 'tt_webid_v2=randomid'
            }
        }
        
        try:
            # Сначала получаем информацию
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info is None:
                    raise ValueError("Could not extract video info")
                
                # Затем загружаем видео
                filename = ydl.prepare_filename(info)
                ydl.download([url])
                
                if os.path.exists(filename):
                    logger.info(f"Video downloaded successfully: {filename}")
                    return filename
                    
                # Проверяем альтернативные расширения
                base, _ = os.path.splitext(filename)
                for ext in ['.mp4', '.webm', '.mkv']:
                    alt_filename = base + ext
                    if os.path.exists(alt_filename):
                        logger.info(f"Video found with different extension: {alt_filename}")
                        return alt_filename
                        
                raise FileNotFoundError("Downloaded video file not found")
                
        except Exception as e:
            logger.error(f"Download failed: {str(e)}")
            raise
                
    except Exception as e:
        logger.error(f"Video download error: {str(e)}")
        raise ValueError(f"Failed to download video: {str(e)}")

    def process_video(self, url: str, target_language: str) -> Tuple[str, str]:
        """Основной процесс обработки видео"""
        try:
            # Загрузка видео
            video_path = self.download_video(url)
            logger.info(f"Video downloaded: {video_path}")
            
            # Извлечение аудио
            audio_path = os.path.join(self.temp_dir, 'audio.mp3')
            video = VideoFileClip(video_path)
            video.audio.write_audiofile(audio_path, codec='mp3', verbose=False)
            video.close()
            logger.info(f"Audio extracted: {audio_path}")
            
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
            logger.info("Transcription completed")
            
            # Генерируем саммари
            language_prompts = {
                'en': 'Generate a comprehensive summary in English:',
                'ru': 'Составьте подробное резюме на русском языке:',
                'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
            }
            
            prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {transcript}"
            summary_response = self.model.generate_content(prompt)
            summary = summary_response.text
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
        logger.error(f"Request processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

# Если запускаем напрямую
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
