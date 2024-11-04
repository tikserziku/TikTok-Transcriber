import os
import asyncio
import logging
from typing import List, Dict, Optional
from pathlib import Path
import time
from pydub import AudioSegment
from datetime import datetime, timedelta
import google.generativeai as genai
import backoff
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, requests_per_minute: int = 15, tokens_per_minute: int = 32000):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.requests_queue = []
        self.tokens_used = 0
        self.last_reset = datetime.now()

    async def wait_for_quota(self, estimated_tokens: int = 1000):
        now = datetime.now()
        
        if now - self.last_reset >= timedelta(minutes=1):
            self.tokens_used = 0
            self.requests_queue = [t for t in self.requests_queue 
                                 if now - t < timedelta(minutes=1)]
            self.last_reset = now

        while (len(self.requests_queue) >= self.requests_per_minute or 
               self.tokens_used + estimated_tokens > self.tokens_per_minute):
            await asyncio.sleep(1)
            now = datetime.now()
            self.requests_queue = [t for t in self.requests_queue 
                                 if now - t < timedelta(minutes=1)]
            
            if now - self.last_reset >= timedelta(minutes=1):
                self.tokens_used = 0
                self.last_reset = now

        self.requests_queue.append(now)
        self.tokens_used += estimated_tokens

class LongVideoProcessor:
    def __init__(self, api_key: str, temp_dir: str = "/tmp/long_video"):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        self.rate_limiter = RateLimiter()
        self.thread_pool = ThreadPoolExecutor(max_workers=2)
        self.processing_results: Dict[str, Dict] = {}

    def cleanup_old_files(self):
        try:
            current_time = time.time()
            for file_path in self.temp_dir.glob("*.mp3"):
                file_age = current_time - os.path.getctime(str(file_path))
                if file_age > 3600:  # 1 hour
                    os.unlink(str(file_path))
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def split_audio(self, audio_path: str, chunk_duration: int = 60) -> List[str]:
        """Разделяет аудио на части по chunk_duration секунд"""
        try:
            audio = AudioSegment.from_mp3(audio_path)
            total_duration = len(audio) / 1000  # в секундах
            chunks = []

            if total_duration <= chunk_duration:
                return [audio_path]

            for i in range(0, len(audio), chunk_duration * 1000):
                chunk = audio[i:i + chunk_duration * 1000]
                chunk_path = str(self.temp_dir / f"chunk_{i//1000}_{int(time.time())}.mp3")
                chunk.export(chunk_path, format="mp3")
                chunks.append(chunk_path)

            logger.info(f"Split audio into {len(chunks)} chunks")
            return chunks

        except Exception as e:
            logger.error(f"Error splitting audio: {e}")
            raise

    async def transcribe_chunk(self, chunk_path: str) -> str:
        """Транскрибирует один аудио чанк"""
        try:
            estimated_tokens = 1000
            await self.rate_limiter.wait_for_quota(estimated_tokens)

            with open(chunk_path, 'rb') as f:
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
            logger.error(f"Error transcribing chunk {chunk_path}: {e}")
            return f"[Error transcribing chunk: {str(e)}]"

    async def process_long_video(self, audio_path: str, request_id: str):
        """Обрабатывает длинное видео"""
        try:
            # Инициализация статуса
            self.processing_results[request_id] = {
                "status": "processing",
                "progress": 0,
                "transcripts": [],
                "error": None
            }

            # Разделение на чанки
            chunks = self.split_audio(audio_path)
            total_chunks = len(chunks)

            # Обработка чанков
            for i, chunk_path in enumerate(chunks):
                try:
                    transcript = await self.transcribe_chunk(chunk_path)
                    self.processing_results[request_id]["transcripts"].append(transcript)
                    self.processing_results[request_id]["progress"] = int((i + 1) * 100 / total_chunks)
                finally:
                    # Удаляем чанк после обработки
                    try:
                        os.unlink(chunk_path)
                    except:
                        pass

            # Объединение результатов
            self.processing_results[request_id]["status"] = "completed"
            self.processing_results[request_id]["final_transcript"] = " ".join(
                self.processing_results[request_id]["transcripts"]
            )

        except Exception as e:
            logger.error(f"Error processing long video: {e}")
            self.processing_results[request_id]["status"] = "failed"
            self.processing_results[request_id]["error"] = str(e)

    def get_processing_status(self, request_id: str) -> Dict:
        """Получает статус обработки"""
        return self.processing_results.get(request_id, {
            "status": "not_found",
            "progress": 0,
            "error": None
        })

    def cleanup(self):
        """Очищает ресурсы"""
        try:
            self.thread_pool.shutdown(wait=True)
            self.cleanup_old_files()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
