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

# Инициализация ThreadPool с меньшим количеством workers для Heroku
thread_pool = ThreadPoolExecutor(max_workers=2)

app = FastAPI()

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Создаем временную директорию в /tmp для Heroku
TEMP_DIR = Path("/tmp/temp_audio")
TEMP_DIR.mkdir(exist_ok=True)

class VideoRequest(BaseModel):
    url: str
    target_language: str

@app.on_event("startup")
async def startup_event():
    logger.info("Application starting up...")
    # Очищаем временную директорию при старте
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        TEMP_DIR.mkdir(exist_ok=True)
    except Exception as e:
        logger.error(f"Error cleaning temp directory on startup: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    # Gracefully закрываем thread pool
    thread_pool.shutdown(wait=True, cancel_futures=True)
    # Очищаем временную директорию
    try:
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
    except Exception as e:
        logger.error(f"Error cleaning temp directory on shutdown: {e}")

async def cleanup_old_files():
    """Очистка старых файлов"""
    try:
        current_time = time.time()
        for file_path in TEMP_DIR.glob("*.mp3"):
            try:
                file_age = current_time - file_path.stat().st_mtime
                # Удаляем файлы старше 15 минут
                if file_age > 900:
                    file_path.unlink()
                    logger.info(f"Removed old file: {file_path}")
            except Exception as e:
                logger.error(f"Error removing file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Error in cleanup: {e}")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        await cleanup_old_files()  # Очищаем старые файлы при каждом запросе
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
        await cleanup_old_files()  # Очищаем старые файлы перед обработкой

        if video_request.target_language not in ['en', 'ru', 'lt']:
            raise HTTPException(status_code=400, detail="Unsupported language")

        try:
            transcript, summary, audio_filename = await asyncio.wait_for(
                run_processing(),
                timeout=25  # Уменьшаем таймаут для Heroku
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
        raise HTTPException(status_code=500, detail="Video processing failed")
    finally:
        processor.cleanup()

@app.post("/extract-audio")
async def extract_audio_endpoint(video_request: VideoRequest):
    processor = TikTokProcessor()
    
    try:
        await cleanup_old_files()

        video_path = await asyncio.wait_for(
            asyncio.to_thread(processor.download_video, video_request.url),
            timeout=15
        )
        
        audio_path = await asyncio.wait_for(
            asyncio.to_thread(processor.extract_audio, video_path),
            timeout=10
        )
        
        timestamp = int(time.time())
        filename = f"audio_{timestamp}.mp3"
        final_audio_path = TEMP_DIR / filename
        shutil.copy2(audio_path, final_audio_path)
        
        return {"audio_path": filename}
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=408, detail="Request Timeout")
    except Exception as e:
        logger.error(f"Audio extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        processor.cleanup()

@app.get("/download-audio/{filename}")
async def download_audio(filename: str):
    try:
        await cleanup_old_files()
        
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
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=1,  # Используем только один worker для Heroku
        log_level="info"
    )
