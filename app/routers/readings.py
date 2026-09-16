from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Reading, ReadingStatus, Section, SectionStatus
from app.schemas import ReadingOut, SectionOut
from app.services.errors import NO_SECTIONS_MESSAGE, map_input_error
from app.services.extractor import extract_from_bytes, extract_from_text
from app.services.limits import (
    InputLimitError,
    read_upload_limited,
    validate_section_count,
    validate_text_size,
    validate_upload_content_type,
)
from app.services.metrics import incr, log_event
from app.services.splitter import split_text
from app.services.tts import build_cache_key
from app.services.worker import enqueue_reading

router = APIRouter(prefix="/api/readings", tags=["readings"])


def _section_out(section: Section) -> SectionOut:
    preview = section.text[:160] + ("…" if len(section.text) > 160 else "")
    return SectionOut(
        id=section.id,
        index=section.index,
        status=section.status,
        char_count=section.char_count,
        error_message=section.error_message,
        preview=preview,
    )


def _reading_out(reading: Reading) -> ReadingOut:
    sections = [_section_out(section) for section in reading.sections]
    return ReadingOut(
        id=reading.id,
        title=reading.title,
        voice_id=reading.voice_id,
        model_id=reading.model_id,
        status=reading.status,
        source_filename=reading.source_filename,
        created_at=reading.created_at,
        updated_at=reading.updated_at,
        sections=sections,
        section_count=len(sections),
        total_char_count=sum(section.char_count for section in reading.sections),
    )


@router.post("", response_model=ReadingOut, status_code=201)
async def create_reading(
    text: str | None = Form(default=None),
    title: str | None = Form(default=None),
    voice_id: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
) -> ReadingOut:
    source_filename = None
    try:
        if file is not None and file.filename:
            validate_upload_content_type(file.content_type)
            data = await read_upload_limited(file)
            if not data:
                raise ValueError("Uploaded file is empty")
            body = extract_from_bytes(file.filename, data)
            source_filename = file.filename
            if not title:
                title = file.filename.rsplit(".", 1)[0]
        elif text:
            validate_text_size(text)
            body = extract_from_text(text)
        else:
            raise ValueError("Provide either text or a .txt/.pdf file")
    except InputLimitError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=map_input_error(exc)) from exc

    chunks = split_text(body)
    if not chunks:
        raise HTTPException(status_code=400, detail=NO_SECTIONS_MESSAGE)
    try:
        validate_section_count(len(chunks))
    except InputLimitError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
    selected_voice = voice_id or settings.elevenlabs_voice_id
    reading = Reading(
        title=(title or "Untitled reading").strip() or "Untitled reading",
        voice_id=selected_voice,
        model_id=settings.elevenlabs_model_id,
        status=ReadingStatus.queued,
        source_filename=source_filename,
    )
    db.add(reading)
    db.flush()

    for index, chunk in enumerate(chunks):
        section = Section(
            reading_id=reading.id,
            index=index,
            text=chunk,
            status=SectionStatus.pending,
            cache_key=build_cache_key(selected_voice, settings.elevenlabs_model_id, chunk),
            char_count=len(chunk),
        )
        db.add(section)

    db.commit()
    db.refresh(reading)
    total_chars = sum(section.char_count for section in reading.sections)
    incr("readings_created")
    incr("sections_queued", len(reading.sections))
    incr("characters_queued", total_chars)
    log_event(
        "reading_created",
        reading_id=reading.id,
        sections=len(reading.sections),
        chars=total_chars,
        voice_id=selected_voice,
        source="file" if source_filename else "text",
    )
    await enqueue_reading(reading.id)
    return _reading_out(reading)


@router.get("/{reading_id}", response_model=ReadingOut)
def get_reading(reading_id: int, db: Session = Depends(get_db)) -> ReadingOut:
    reading = db.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    return _reading_out(reading)
