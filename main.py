# main.py
import os
import tempfile
import logging
import shutil
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import google.generativeai as genai
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import yt_dlp
from langdetect import detect

# Инициализация FastAPI
app = FastAPI()

# HTML шаблон для главной страницы
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
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="mb-4">📱 TikTok Transcriber</h1>
        
        <div class="row mb-3">
            <div class="col">
                <input type="text" id="tiktokUrl" class="form-control" placeholder="Вставьте ссылку на TikTok видео">
            </div>
        </div>
        
        <div class="row mb-3">
            <div class="col">
                <select id="language" class="form-select">
                    <option value="en">English</option>
                    <option value="ru">Русский</option>
                    <option value="lt">Lietuvių</option>
                </select>
            </div>
            <div class="col">
                <button onclick="processVideo()" class="btn btn-primary">Обработать</button>
            </div>
        </div>
        
        <div class="row">
            <div class="col-md-6">
                <h3>Transcription</h3>
                <div id="transcription" class="result-box">
                    <button onclick="copyText('transcription')" class="btn btn-sm btn-secondary">Copy</button>
                    <div class="content"></div>
                </div>
            </div>
            <div class="col-md-6">
                <h3>Summary</h3>
                <div id="summary" class="result-box">
                    <button onclick="copyText('summary')" class="btn btn-sm btn-secondary">Copy</button>
                    <div class="content"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        async function processVideo() {
            const url = document.getElementById('tiktokUrl').value;
            const lang = document.getElementById('language').value;
            
            // Показываем статус загрузки
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
                
                const data = await response.json();
                
                document.getElementById('transcription').querySelector('.content').innerText = data.transcription;
                document.getElementById('summary').querySelector('.content').innerText = data.summary;
            } catch (error) {
                alert('Error processing video: ' + error);
            }
        }
        
        function copyText(elementId) {
            const text = document.getElementById(elementId).querySelector('.content').innerText;
            navigator.clipboard.writeText(text);
        }
    </script>
</body>
</html>
"""

# Модель для входных данных
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

    def process_video(self, url: str, target_language: str):
        try:
            # Загрузка видео
            video_path = self._download_video(url)
            
            # Извлечение аудио
            audio_path = self._extract_audio(video_path)
            
            # Транскрибация
            transcript = self._transcribe_audio(audio_path)
            
            # Саммари
            summary = self._generate_summary(transcript, target_language)
            
            return transcript, summary
            
        finally:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                self.temp_dir = tempfile.mkdtemp()

    def _download_video(self, url: str) -> str:
        file_id = os.urandom(4).hex()
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(self.temp_dir, f'video_{file_id}.%(ext)s'),
            'quiet': True
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)

    def _extract_audio(self, video_path: str) -> str:
        video = VideoFileClip(video_path)
        audio_path = os.path.join(self.temp_dir, 'audio.mp3')
        video.audio.write_audiofile(audio_path, codec='mp3', verbose=False)
        video.close()
        return audio_path

    def _transcribe_audio(self, audio_path: str) -> str:
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

    def _generate_summary(self, text: str, target_language: str) -> str:
        language_prompts = {
            'en': 'Generate a comprehensive summary in English:',
            'ru': 'Составьте подробное резюме на русском языке:',
            'lt': 'Sukurkite išsamią santrauką lietuvių kalba:'
        }
        
        prompt = f"{language_prompts.get(target_language, language_prompts['en'])} {text}"
        response = self.model.generate_content(prompt)
        return response.text

# Маршруты FastAPI
@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTML_TEMPLATE

@app.post("/process")
async def process_video(request: VideoRequest):
    processor = TikTokProcessor()
    try:
        transcript, summary = processor.process_video(request.url, request.target_language)
        return {"transcription": transcript, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

