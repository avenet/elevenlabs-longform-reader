import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routers import audio, readings, voices
from app.services.errors import GENERIC_INTERNAL_MESSAGE, log_internal_error
from app.services.metrics import snapshot
from app.services.storage import ensure_storage
from app.services.worker import queue_depth, recover_pending, start_worker

STATIC_DIR = Path(__file__).resolve().parent / "static"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_storage()
    init_db()
    await start_worker()
    await recover_pending()
    yield


app = FastAPI(title="Long-form Reading Service", lifespan=lifespan)
app.include_router(readings.router)
app.include_router(audio.router)
app.include_router(voices.router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(Exception)
async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    log_internal_error(exc)
    return JSONResponse(status_code=500, content={"detail": GENERIC_INTERNAL_MESSAGE})


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


@app.get("/api/metrics")
def get_metrics() -> dict:
    counters = snapshot()
    hits = counters.get("tts_cache_hits", 0)
    misses = counters.get("tts_cache_misses", 0)
    total = hits + misses
    return {
        "counters": counters,
        "queue_depth": queue_depth(),
        "cache_hit_rate": (hits / total) if total else None,
    }
