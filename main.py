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

# Инициализация приложения и компонентов
app = FastAPI()
thread_pool = ThreadPoolExecutor(max_workers=3)

# Настройка статических файлов и шаблонов
static_path = Path(__file__).parent / "static"
if not static_path.exists():
    static_path.mkdir(parents=True)

app.mount("/static", StaticFiles(directory=str(static_path)), name="static")
templates = Jinja2Templates(directory="templates")

# Настройка временной директории
TEMP_DIR = Path("/tmp/temp_audio")
TEMP_DIR.mkdir(exist_ok=True)

# Глобальные флаги
is_shutting_down = False

class VideoRequest(BaseModel):
    url: str
    target_language: str

def cleanup_resources():
    """Очистка ресурсов при выключении"""
    global is_shutting_down
    is_shutting_down = True
    
    logger.info("Cleaning up resources...")
    try:
        thread_pool.shutdown(wait=True)
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
            TEMP_DIR.mkdir(exist_ok=True)
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Регистрация обработчиков
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
    signal.signal(sig, lambda signum, frame: cleanup_resources())
atexit.register(cleanup_resources)

@app.on_event("startup")
async def startup_event():
    global is_shutting_down
    is_shutting_down = False
    logger.info("Application starting up...")
    TEMP_DIR.mkdir(exist_ok=True)

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    cleanup_resources()

async def cleanup_old_files():
    """Очистка старых файлов"""
    if is_shutting_down:
        return
        
    try:
        current_time = time.time()
        for file_path in TEMP_DIR.glob("*.mp3"):
            try:
                file_age = current_time - os.path.getctime(str(file_path))
                if file_age > 3600:  # 1 час
                    os.unlink(str(file_path))
                    logger.info(f"Removed old file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

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
        raise HTTPException(status_code=503, detail="Service is shutting down")

    processor = TikTokProcessor()
    try:
        # Проверка языка
        if video_request.target_language not in ['en', 'ru', 'lt']:
            raise HTTPException(status_code=400, detail="Unsupported language")

        # Обработка видео
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

        response_data = {
            "transcription": transcript,
            "summary": summary
        }
        
        if audio_filename:
            response_data["audio_path"] = audio_filename

        return response_data

    except ValueError as e:
        if "too long" in str(e):
            return {
                "transcription": str(e),
                "summary": "Video too long for automatic processing",
                "audio_path": processor.get_extracted_audio_path()
            }
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Processing error: {e}")
        # Пытаемся вернуть хотя бы аудио при ошибке
        audio_path = processor.get_extracted_audio_path()
        if audio_path and os.path.exists(audio_path):
            timestamp = int(time.time())
            filename = f"audio_{timestamp}.mp3"
            final_audio_path = TEMP_DIR / filename
            shutil.copy2(audio_path, final_audio_path)
            return {
                "transcription": "Processing failed",
                "summary": "Processing failed",
                "audio_path": filename
            }
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if not is_shutting_down:
            await cleanup_old_files()
        processor.cleanup()

@app.post("/extract-audio")
async def extract_audio_endpoint(video_request: VideoRequest):
    """Извлечение аудио из видео"""
    if is_shutting_down:
        raise HTTPException(status_code=503, detail="Service is shutting down")
        
    processor = TikTokProcessor()
    try:
        # Загрузка и извлечение
        video_path = await processor.download_video(video_request.url)
        audio_path = await processor.extract_audio(video_path)
        
        # Сохранение файла
        timestamp = int(time.time())
        filename = f"audio_{timestamp}.mp3"
        final_audio_path = TEMP_DIR / filename
        
        shutil.copy2(audio_path, final_audio_path)
        
        return {
            "audio_path": filename,
            "size_mb": os.path.getsize(final_audio_path) / (1024*1024),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        processor.cleanup()

@app.get("/download-audio/{filename}")
async def download_audio(filename: str):
    """Скачивание аудио файла"""
    if is_shutting_down:
        raise HTTPException(status_code=503, detail="Service is shutting down")
        
    try:
        file_path = TEMP_DIR / filename
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
