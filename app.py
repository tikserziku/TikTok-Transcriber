import os
import tempfile
import logging
import shutil
from typing import Optional, Tuple
import google.generativeai as genai
from dotenv import load_dotenv
import gradio as gr
from moviepy.editor import VideoFileClip
from pydub import AudioSegment
import yt_dlp
from langdetect import detect

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TikTokTranscriber:
    def __init__(self):
        # Инициализация Google AI
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("Google API key not found in environment variables")
        
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temp_dir = tempfile.mkdtemp()

    def download_tiktok(self, url: str) -> str:
        """Загрузка видео из TikTok"""
        ydl_opts = {
            'format': 'best',
            'outtmpl': os.path.join(self.temp_dir, '%(title)s.%(ext)s'),
            'quiet': True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            raise

    def extract_audio(self, video_path: str) -> str:
        """Извлечение аудио из видео"""
        try:
            video = VideoFileClip(video_path)
            audio_path = os.path.join(self.temp_dir, 'audio.mp3')
            video.audio.write_audiofile(audio_path, codec='mp3', verbose=False, logger=None)
            video.close()
            return audio_path
        except Exception as e:
            logger.error(f"Audio extraction error: {e}")
            raise

    def optimize_audio(self, audio_path: str) -> str:
        """Оптимизация аудио для транскрибации"""
        try:
            audio = AudioSegment.from_file(audio_path)
            if audio.channels > 1:
                audio = audio.set_channels(1)
            audio = audio.set_frame_rate(16000)
            audio = audio.normalize()
            
            optimized_path = os.path.join(self.temp_dir, 'optimized_audio.mp3')
            audio.export(optimized_path, format='mp3')
            return optimized_path
        except Exception as e:
            logger.error(f"Audio optimization error: {e}")
            raise

    def transcribe_audio(self, audio_path: str) -> str:
        """Транскрибация аудио"""
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
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            raise

    def generate_summary(self, text: str) -> str:
        """Генерация саммари из транскрибации"""
        try:
            detected_lang = detect(text)
            prompt = f"Generate a comprehensive but concise summary in the same language ({detected_lang}) of the following text:\n\n{text}"
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Summary generation error: {e}")
            raise

    def process_url(self, url: str, progress=gr.Progress()) -> Tuple[str, str]:
        """Основной процесс обработки URL"""
        try:
            # Загрузка видео
            progress(0.2, desc="Downloading TikTok video...")
            video_path = self.download_tiktok(url)
            
            # Извлечение и оптимизация аудио
            progress(0.4, desc="Extracting audio...")
            audio_path = self.extract_audio(video_path)
            optimized_audio = self.optimize_audio(audio_path)
            
            # Транскрибация
            progress(0.6, desc="Transcribing audio...")
            transcript = self.transcribe_audio(optimized_audio)
            
            # Генерация саммари
            progress(0.8, desc="Generating summary...")
            summary = self.generate_summary(transcript)
            
            progress(1.0, desc="Done!")
            return transcript, summary
            
        except Exception as e:
            logger.error(f"Processing error: {e}")
            return f"Error: {str(e)}", ""
        finally:
            # Очистка временных файлов
            try:
                if os.path.exists(self.temp_dir):
                    shutil.rmtree(self.temp_dir)
                self.temp_dir = tempfile.mkdtemp()
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

def create_interface():
    """Создание веб-интерфейса"""
    transcriber = TikTokTranscriber()
    
    with gr.Blocks(theme=gr.themes.Soft()) as interface:
        gr.Markdown("""
        # 📱 TikTok Transcriber
        Введите ссылку на TikTok видео для получения транскрипции и саммари
        """)
        
        with gr.Row():
            url_input = gr.Textbox(
                label="TikTok URL",
                placeholder="https://vm.tiktok.com/... или https://www.tiktok.com/...",
                scale=4
            )
            paste_btn = gr.Button("📋 PASTE", scale=1)
            process_btn = gr.Button("🎯 Process", scale=1, variant="primary")
            
        with gr.Row():
            # Колонка с транскрипцией
            with gr.Column():
                transcript_output = gr.Textbox(
                    label="Transcription",
                    placeholder="Transcription will appear here...",
                    lines=10,
                    show_copy_button=True
                )
            
            # Колонка с саммари
            with gr.Column():
                summary_output = gr.Textbox(
                    label="Summary",
                    placeholder="Summary will appear here...",
                    lines=10,
                    show_copy_button=True
                )
        
        # Убираем JavaScript и добавляем простую функцию для paste
        def paste_from_clipboard():
            return ""  # В веб-интерфейсе пользователь будет использовать Ctrl+V
        
        # Обработчики событий
        paste_btn.click(
            fn=paste_from_clipboard,
            inputs=None,
            outputs=url_input
        )
        
        process_btn.click(
            fn=transcriber.process_url,
            inputs=[url_input],
            outputs=[transcript_output, summary_output],
        )
        
        gr.Markdown("""
        ### 📝 Инструкция:
        1. Вставьте ссылку на видео TikTok (используйте Ctrl+V или введите вручную)
        2. Нажмите Process для начала обработки
        3. Дождитесь результатов
        4. Используйте кнопки копирования для сохранения текста
        """)
    
    return interface

if __name__ == "__main__":
    app = create_interface()
    port = int(os.environ.get("PORT", 7860))
    app.launch(server_name="0.0.0.0", server_port=port)
