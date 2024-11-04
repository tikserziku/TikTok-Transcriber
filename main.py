from fastapi.responses import FileResponse
import os
from pathlib import Path
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging
import shutil
import time
from processor import TikTokProcessor
from concurrent.futures import ThreadPoolExecutor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация ThreadPool для асинхронных операций
thread_pool = ThreadPoolExecutor(max_workers=3)

app = FastAPI()

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class VideoRequest(BaseModel):
    url: str
    target_language: str


@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Создаем директорию для аудио файлов при запуске
    Path("temp_audio").mkdir(exist_ok=True)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    thread_pool.shutdown(wait=False)
    # Очищаем временную директорию при выключении
    try:
        shutil.rmtree("temp_audio")
    except Exception as e:
        logger.error(f"Error cleaning temp directory: {e}")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/process")
async def process_video(video_request: VideoRequest):
    processor = TikTokProcessor()

    async def run_processing():
        try:
            transcript, summary, audio_path = await asyncio.to_thread(
                processor.process_video,
                video_request.url,
                video_request.target_language
            )
            
            # Сохраняем аудио файл если он есть
            audio_filename = None
            if audio_path and os.path.exists(audio_path):
                timestamp = int(time.time())
                filename = f"audio_{timestamp}.mp3"
                final_audio_path = Path("temp_audio") / filename
                shutil.copy2(audio_path, final_audio_path)
                audio_filename = filename
                
            return transcript, summary, audio_filename
            
        except Exception as e:
            logger.error(f"Processing error in thread: {e}")
            raise

    try:
        # Проверка языка
        valid_languages = ['en', 'ru', 'lt']
        if video_request.target_language not in valid_languages:
            raise HTTPException(status_code=400, detail="Unsupported language")

        # Обработка с таймаутом
        try:
            transcript, summary, audio_filename = await asyncio.wait_for(
                run_processing(),
                timeout=300
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="Request Timeout")

        response_data = {
            "transcription": transcript,
            "summary": summary
        }
        
        if audio_filename:
            response_data["audio_path"] = audio_filename

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {e}")
        # Проверяем, есть ли доступный аудио файл даже при ошибке
        audio_path = processor.get_extracted_audio_path()
        if audio_path and os.path.exists(audio_path):
            timestamp = int(time.time())
            filename = f"audio_{timestamp}.mp3"
            final_audio_path = Path("temp_audio") / filename
            shutil.copy2(audio_path, final_audio_path)
            return {
                "transcription": "Processing failed",
                "summary": "Processing failed",
                "audio_path": filename
            }
        raise HTTPException(status_code=500, detail="Video processing failed")
    finally:
        processor.cleanup()


@app.post("/extract-audio")
async def extract_audio_endpoint(video_request: VideoRequest):
    processor = TikTokProcessor()
    
    try:
        # Загружаем видео и извлекаем аудио
        video_path = await asyncio.to_thread(processor.download_video, video_request.url)
        audio_path = await asyncio.to_thread(processor.extract_audio, video_path)
        
        # Сохраняем аудио файл во временную директорию
        timestamp = int(time.time())
        filename = f"audio_{timestamp}.mp3"
        final_audio_path = Path("temp_audio") / filename
        shutil.copy2(audio_path, final_audio_path)
        
        return {"audio_path": filename}
        
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        processor.cleanup()


@app.get("/download-audio/{filename}")
async def download_audio(filename: str):
    try:
        file_path = Path("temp_audio") / filename
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Audio file not found")
            
        return FileResponse(
            path=file_path,
            media_type="audio/mpeg",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.on_event("startup")
async def cleanup_old_files():
    """Периодически очищает старые временные файлы"""
    while True:
        try:
            temp_dir = Path("temp_audio")
            current_time = time.time()
            
            for file_path in temp_dir.glob("*.mp3"):
                file_age = current_time - os.path.getctime(file_path)
                # Удаляем файлы старше 1 часа
                if file_age > 3600:
                    try:
                        os.unlink(file_path)
                        logger.info(f"Removed old file: {file_path}")
                    except Exception as e:
                        logger.error(f"Error removing old file {file_path}: {e}")
                        
        except Exception as e:
            logger.error(f"Error in cleanup task: {e}")
            
        await asyncio.sleep(3600)  # Проверяем каждый час


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
