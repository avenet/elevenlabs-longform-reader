from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Reading, SectionStatus
from app.services.errors import (
    AUDIO_NOT_READY_MESSAGE,
    READING_NOT_FOUND_MESSAGE,
)

router = APIRouter(prefix="/api/readings", tags=["audio"])


@router.get("/{reading_id}/sections/{index}/audio")
def stream_section_audio(
    reading_id: int,
    index: int,
    db: Session = Depends(get_db),
) -> FileResponse:
    reading = db.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail=READING_NOT_FOUND_MESSAGE)

    section = next((s for s in reading.sections if s.index == index), None)
    if section is None:
        raise HTTPException(status_code=404, detail="Section not found")

    if section.status != SectionStatus.ready or not section.audio_path:
        raise HTTPException(status_code=404, detail=AUDIO_NOT_READY_MESSAGE)

    path = Path(section.audio_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Audio file missing")

    return FileResponse(
        path,
        media_type="audio/mpeg",
        filename=f"reading-{reading_id}-section-{index}.mp3",
        headers={"Accept-Ranges": "bytes", "Cache-Control": "public, max-age=3600"},
    )
