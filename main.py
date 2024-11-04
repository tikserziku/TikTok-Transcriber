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
import atexit
import signal
from long_routes import router as long_video_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Инициализация ThreadPool
thread_pool = ThreadPoolExecutor(max_workers=3)

app = FastAPI()

# Подключаем роутер для длинных видео
app.include_router(long_video_router, prefix="/long", tags=["long_videos"])

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Создаем временную директорию в /tmp
TEMP_DIR = Path("/tmp/temp_audio")
TEMP_DIR.mkdir(exist_ok=True)

# Глобальный флаг для отслеживания состояния приложения
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
        # Завершаем thread pool
        thread_pool.shutdown(wait=True)
        
        # Очищаем временные файлы
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
            TEMP_DIR.mkdir(exist_ok=True)
            
        logger.info("Cleanup completed successfully")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

# Регистрируем обработчики сигналов
for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGQUIT):
    signal.signal(sig, lambda signum, frame: cleanup_resources())

# Регистрируем cleanup при выходе
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
            if is_shutting_down:
                break
            try:
                file_age = current_time - os.path.getctime(str(file_path))
                if file_age > 3600:  # Удаляем файлы старше часа
                    os.unlink(str(file_path))
                    logger.info(f"Removed old file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/process")
async def process_video(video_request: VideoRequest):
    if is_shutting_down:
        raise HTTPException(status_code=503, detail="Service is shutting down")

    processor = TikTokProcessor()

    async def run_processing():
        try:
            transcript, summary, audio_path = await asyncio.to_thread(
                processor.process_video,
                video_request.url,
                video_request.target_language
            )
            
            if is_shutting_down:
                raise HTTPException(status_code=503, detail="Service is shutting down")
                
            audio_filename = None
            if audio_path and os.path.exists(audio_path):
                timestamp = int(time.time())
                filename = f"audio_{timestamp}.mp3"
                final_audio_path = TEMP_DIR / filename
                shutil.copy2(audio_path, final_audio_path)
                audio_filename = filename
                
            return transcript, summary, audio_filename
        except Exception as e:
            logger.error(f"Processing error in thread: {e}")
            raise

    try:
        if video_request.target_language not in ['en', 'ru', 'lt']:
            raise HTTPException(status_code=400, detail="Unsupported language")

        transcript, summary, audio_filename = await asyncio.wait_for(
            run_processing(),
            timeout=290  # Чуть меньше, чем таймаут Gunicorn
        )

        response_data = {
            "transcription": transcript,
            "summary": summary
        }
        
        if audio_filename:
            response_data["audio_path"] = audio_filename

        return response_data

    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request Timeout")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {e}")
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
    if is_shutting_down:
        raise HTTPException(status_code=503, detail="Service is shutting down")
        
    processor = TikTokProcessor()
    
    try:
        video_path = await asyncio.to_thread(processor.download_video, video_request.url)
        audio_path = await asyncio.to_thread(processor.extract_audio, video_path)
        
        if is_shutting_down:
            raise HTTPException(status_code=503, detail="Service is shutting down")
            
        timestamp = int(time.time())
        filename = f"audio_{timestamp}.mp3"
        final_audio_path = TEMP_DIR / filename
        shutil.copy2(audio_path, final_audio_path)
        
        return {"audio_path": filename}
        
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if not is_shutting_down:
            await cleanup_old_files()
        processor.cleanup()

@app.get("/download-audio/{filename}")
async def download_audio(filename: str):
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
