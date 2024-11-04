import asyncio
import tempfile
import os
import logging
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse  # Add StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

from processor import TikTokProcessor
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

thread_pool = ThreadPoolExecutor(max_workers=3)
app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Set up templates
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
async def read_root(request: Request): # Use request object for template rendering
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/process")
async def process_video_route(request: Request):
    try:
        video_request = await request.json()
        url = video_request.get('url')
        target_language = video_request.get('target_language')

        valid_languages = ['en', 'ru', 'lt']
        if target_language not in valid_languages:
            raise HTTPException(status_code=400, detail="Unsupported language")

        processor = TikTokProcessor()
        transcript, summary, audio_filepath = await asyncio.to_thread(
            processor.process_video, url, target_language
        )

        audio_filename = os.path.basename(audio_filepath)

        return {
            "transcription": transcript,
            "summary": summary,
            "audio_url": f"/download/{audio_filename}",
            "audio_filename": audio_filename # Include filename if needed in frontend.
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Video processing failed: {e}")
    finally:
        processor.cleanup()


@app.get("/download/{filename}")
async def download_audio(filename: str):
    audio_filepath = os.path.join(tempfile.gettempdir(), filename) # Or wherever your audio is stored
    if os.path.exists(audio_filepath):
        def iterfile():
            with open(audio_filepath, mode="rb") as file_like:
                yield from file_like

        return StreamingResponse(iterfile(), media_type="audio/mpeg", headers={"Content-Disposition": f"attachment; filename={filename}"})
    else:
        raise HTTPException(status_code=404, detail="Audio file not found")



if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
