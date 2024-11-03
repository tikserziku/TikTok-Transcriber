from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import logging
from processor import TikTokProcessor
import os

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Подключаем статические файлы и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

class VideoRequest(BaseModel):
    url: str
    target_language: str

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):  # Добавляем аннотацию типа Request
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process")
async def process_video(request: VideoRequest):
    processor = TikTokProcessor()
    try:
        transcript, summary = processor.process_video(request.url, request.target_language)
        return {
            "transcription": transcript,
            "summary": summary
        }
    except Exception as e:
        logger.error(f"Request processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
