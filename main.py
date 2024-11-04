from fastapi.responses import FileResponse, JSONResponse
import os
from pathlib import Path
import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor
import atexit
import signal
from app.processor import TikTokProcessor

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация приложения
app = FastAPI()

# Добавляем CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Инициализация компонентов
thread_pool = ThreadPoolExecutor(max_workers=3)

# Настройка статических файлов и шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Настройка временной директории
TEMP_DIR = Path("/tmp/temp_audio")
TEMP_DIR.mkdir(exist_ok=True, parents=True)

# Глобальные флаги
is_shutting_down = False

class VideoRequest(BaseModel):
    url: str
    target_language: str

def cleanup_resources():
    """Очистка ресурсов при выключении"""
    global is_shutting_down
    try:
        is_shutting_down = True
        logger.info("Cleaning up resources...")
        
        # Корректное завершение thread pool
        thread_pool.shutdown(wait=False)
        
        # Очистка временных файлов
        if TEMP_DIR.exists():
            try:
                shutil.rmtree(TEMP_DIR)
                TEMP_DIR.mkdir(exist_ok=True)
            except Exception as e:
                logger.warning(f"Error cleaning temp directory: {e}")
                
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Регистрация обработчиков завершения
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_resources())
atexit.register(cleanup_resources)

@app.on_event("startup")
async def startup_event():
    global is_shutting_down
    is_shutting_down = False
    logger.info("Application starting up...")
    TEMP_DIR.mkdir(exist_ok=True, parents=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    await asyncio.get_event_loop().run_in_executor(None, cleanup_resources)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Главная страница"""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/process")
async def process_video(video_request: VideoRequest):
    """Обработка видео"""
    if is_shutting_down:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service is shutting down"}
        )

    processor = None
    try:
        if video_request.target_language not in ['en', 'ru', 'lt']:
            return JSONResponse(
                status_code=400,
                content={"detail": "Unsupported language"}
            )

        processor = TikTokProcessor()
        transcript, summary, audio_path = await processor.process_video(
            video_request.url,
            video_request.target_language
        )

        # Сохранение аудио если оно есть
        audio_filename = None
        if audio_path and os.path.exists(audio_path):
            timestamp = int(time.time())
            filename = f"audio_{timestamp}.mp3"
            final_audio_path = TEMP_DIR / filename
            shutil.copy2(audio_path, final_audio_path)
            audio_filename = filename

        return JSONResponse(content={
            "transcription": transcript,
            "summary": summary,
            "audio_path": audio_filename
        })

    except ValueError as e:
        if "too long" in str(e):
            return JSONResponse(content={
                "transcription": str(e),
                "summary": "Video too long for automatic processing",
                "audio_path": processor.get_extracted_audio_path() if processor else None
            })
        return JSONResponse(
            status_code=400,
            content={"detail": str(e)}
        )
    except Exception as e:
        logger.error(f"Processing error: {e}")
        if processor:
            # Пытаемся сохранить аудио при ошибке
            try:
                audio_path = processor.get_extracted_audio_path()
                if audio_path and os.path.exists(audio_path):
                    timestamp = int(time.time())
                    filename = f"audio_{timestamp}.mp3"
                    final_audio_path = TEMP_DIR / filename
                    shutil.copy2(audio_path, final_audio_path)
                    return JSONResponse(content={
                        "transcription": "Processing failed",
                        "summary": "Processing failed",
                        "audio_path": filename
                    })
            except Exception as save_error:
                logger.error(f"Error saving audio: {save_error}")
        
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        if processor:
            processor.cleanup()

@app.post("/extract-audio")
async def extract_audio_endpoint(video_request: VideoRequest):
    if is_shutting_down:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service is shutting down"}
        )
        
    processor = None
    try:
        processor = TikTokProcessor()
        
        # Используем обычную функцию для скачивания, так как она уже реализована синхронно
        video_path = processor.download_video(video_request.url)
        logger.info(f"Video downloaded: {video_path}")
        
        # Используем обычную функцию для извлечения аудио
        audio_path = processor.extract_audio(video_path)
        logger.info(f"Audio extracted: {audio_path}")
        
        # Создаем временную директорию если её нет
        if not TEMP_DIR.exists():
            TEMP_DIR.mkdir(parents=True)
        
        # Копируем файл с уникальным именем
        timestamp = int(time.time())
        filename = f"audio_{timestamp}.mp3"
        final_audio_path = TEMP_DIR / filename
        shutil.copy2(audio_path, final_audio_path)
        
        # Получаем размер файла
        file_size = os.path.getsize(final_audio_path) / (1024 * 1024)  # в МБ
        
        return JSONResponse(content={
            "audio_path": filename,
            "size_mb": file_size,
            "status": "success"
        })
        
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )
    finally:
        if processor:
            processor.cleanup()

@app.get("/download-audio/{filename}")
async def download_audio(filename: str):
    """Скачивание аудио файла"""
    if is_shutting_down:
        return JSONResponse(
            status_code=503,
            content={"detail": "Service is shutting down"}
        )
        
    try:
        file_path = TEMP_DIR / filename
        if not file_path.exists():
            return JSONResponse(
                status_code=404,
                content={"detail": "Audio file not found"}
            )
            
        return FileResponse(
            path=file_path,
            media_type="audio/mpeg",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
        
    except Exception as e:
        logger.error(f"Download error: {e}")
        return JSONResponse(
            status_code=500,
            content={"detail": str(e)}
        )

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
