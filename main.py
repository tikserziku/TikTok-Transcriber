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
        logger.error(f"Error rendering index page: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.post("/process")
async def process_video(video_request: VideoRequest):
    processor = TikTokProcessor()

    async def run_processing():
        try:
            result = await asyncio.to_thread(
                processor.process_video,
                video_request.url,
                video_request.target_language
            )
            return result
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
            transcript, summary = await asyncio.wait_for(
                run_processing(),
                timeout=300
            )
        except asyncio.TimeoutError:
            raise HTTPException(status_code=408, detail="Request Timeout")

        return {
            "transcription": transcript,
            "summary": summary
        }

    except HTTPException:
        raise  # Re-raise HTTPExceptions
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail="Video processing failed")
    finally:
        processor.cleanup()


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )
