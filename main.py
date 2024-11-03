import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging
import os
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

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutting down...")
    thread_pool.shutdown(wait=False)

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

async def process_in_thread(processor: TikTokProcessor, url: str, target_language: str):
    """Выполнение обработки в отдельном потоке"""
    try:
        return await asyncio.get_event_loop().run_in_executor(
            thread_pool,
            processor.process_video,
            url,
            target_language
        )
    except Exception as e:
        logger.error(f"Thread processing error: {str(e)}")
        raise

@app.post("/process")
async def process_video(request: VideoRequest):
    processor = TikTokProcessor()
    try:
        # Проверка языка
        valid_languages = ['en', 'ru', 'lt']
        if request.target_language not in valid_languages:
            raise ValueError("Неподдерживаемый язык")

        # Обработка в отдельном потоке с таймаутом
        try:
            transcript, summary = await asyncio.wait_for(
                process_in_thread(processor, request.url, request.target_language),
                timeout=300
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="Превышено время ожидания запроса")
        
        return {
            "transcription": transcript,
            "summary": summary
        }
        
    except ValueError as ve:
        logger.warning(f"Validation error: {str(ve)}")
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка при обработке видео")
    finally:
        # Очистка временных файлов
        try:
            if hasattr(processor, 'cleanup'):
                await asyncio.get_event_loop().run_in_executor(
                    thread_pool,
                    processor.cleanup
                )
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        workers=2,
        loop="asyncio",
        timeout_keep_alive=120,
        access_log=True,
        log_level="info"
    )
