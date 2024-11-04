from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import asyncio
import os
import time
from typing import Optional
from pathlib import Path
import logging

# Обновляем импорты
from .processor import TikTokProcessor
from .long_processor import LongVideoProcessor

logger = logging.getLogger(__name__)

router = APIRouter()

# Инициализация процессора при старте
processor = LongVideoProcessor(api_key=os.getenv('GOOGLE_API_KEY'))

class LongVideoRequest(BaseModel):
    url: str
    target_language: str
    mode: str = "auto"  # "auto", "force_split", "no_split"

@router.post("/process-long")
async def process_long_video(request: LongVideoRequest):
    """Эндпоинт для обработки длинных видео"""
    try:
        # Создаем обычный процессор для загрузки видео
        tiktok_processor = TikTokProcessor()
        
        # Загружаем видео и извлекаем аудио
        video_path = await asyncio.to_thread(
            tiktok_processor.download_video,
            request.url
        )
        audio_path = await asyncio.to_thread(
            tiktok_processor.extract_audio,
            video_path
        )

        # Генерируем ID запроса
        request_id = f"req_{int(time.time())}_{os.urandom(4).hex()}"

        # Запускаем асинхронную обработку
        asyncio.create_task(processor.process_long_video(audio_path, request_id))

        return {
            "request_id": request_id,
            "status": "processing",
            "message": "Processing started"
        }

    except Exception as e:
        logger.error(f"Error initiating long video processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        tiktok_processor.cleanup()

@router.get("/status/{request_id}")
async def get_processing_status(request_id: str):
    """Получение статуса обработки"""
    status = processor.get_processing_status(request_id)
    
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Request not found")
        
    return status

@router.get("/result/{request_id}")
async def get_processing_result(request_id: str):
    """Получение результата обработки"""
    status = processor.get_processing_status(request_id)
    
    if status["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Request not found")
        
    if status["status"] == "processing":
        raise HTTPException(status_code=102, detail="Processing in progress")
        
    if status["status"] == "failed":
        raise HTTPException(status_code=500, detail=status["error"])
        
    return {
        "transcript": status.get("final_transcript", ""),
        "chunks_processed": len(status.get("transcripts", [])),
        "status": "completed"
    }
