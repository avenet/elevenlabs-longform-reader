from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import audio, readings, voices
from app.services.storage import ensure_storage
from app.services.worker import start_worker

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    init_db()
    await start_worker()
    yield


app = FastAPI(title="Long-form Reading Service", lifespan=lifespan)
app.include_router(readings.router)
app.include_router(audio.router)
app.include_router(voices.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")
