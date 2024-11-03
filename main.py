import asyncio
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging
from processor import TikTokProcessor
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="TikTok Transcriber",
    description="Application for transcribing and summarizing TikTok videos",
    version="1.0.0"
)

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class VideoRequest(BaseModel):
    url: str
    target_language: str

# Обработчики ошибок
@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "errors/404.html",
        {
            "request": request,
            "message": "Запрашиваемая страница не найдена"
        },
        status_code=404
    )

@app.exception_handler(500)
async def server_error_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "errors/500.html",
        {
            "request": request,
            "message": "Внутренняя ошибка сервера"
        },
        status_code=500
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse(
        "errors/error.html",
        {
            "request": request,
            "status_code": exc.status_code,
            "message": exc.detail
        },
        status_code=exc.status_code
    )

# Обработчик ошибок валидации
@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": str(exc)}
    )

# Основные маршруты
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/process")
async def process_video(request: VideoRequest):
    processor = TikTokProcessor()
    try:
        # Проверка языка
        valid_languages = ['en', 'ru', 'lt']
        if request.target_language not in valid_languages:
            raise ValueError("Неподдерживаемый язык")

        # Устанавливаем таймаут на 5 минут
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(processor.process_video, request.url, request.target_language),
                timeout=300
            )
            transcript, summary = response
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
            processor.cleanup()
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")

# Middleware для логирования запросов
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"Request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Response status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {str(e)}")
        raise

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    
    # Настройки для uvicorn
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        reload=True if os.getenv("DEBUG") else False
    )
    
    server = uvicorn.Server(config)
    server.run()
