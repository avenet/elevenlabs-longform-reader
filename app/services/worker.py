import asyncio
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Reading, ReadingStatus, Section, SectionStatus
from app.services.storage import section_audio_path
from app.services.tts import generate_speech

_executor = ThreadPoolExecutor(max_workers=settings.worker_concurrency)
_queue: asyncio.Queue[int] | None = None
_worker_task: asyncio.Task | None = None
_active_readings: set[int] = set()


def compute_reading_status(sections: list[Section]) -> ReadingStatus:
    if not sections:
        return ReadingStatus.failed

    statuses = {section.status for section in sections}
    if statuses == {SectionStatus.ready}:
        return ReadingStatus.ready
    if statuses == {SectionStatus.failed}:
        return ReadingStatus.failed
    if SectionStatus.ready in statuses and (
        SectionStatus.failed in statuses
        or SectionStatus.pending in statuses
        or SectionStatus.processing in statuses
    ):
        if SectionStatus.pending in statuses or SectionStatus.processing in statuses:
            return ReadingStatus.processing
        return ReadingStatus.partial
    if SectionStatus.processing in statuses or SectionStatus.pending in statuses:
        if SectionStatus.ready in statuses or SectionStatus.failed in statuses:
            return ReadingStatus.processing
        return ReadingStatus.processing if SectionStatus.processing in statuses else ReadingStatus.queued
    return ReadingStatus.partial


async def _process_section(section_id: int) -> None:
    db: Session = SessionLocal()
    try:
        section = db.get(Section, section_id)
        if section is None:
            return

        reading = db.get(Reading, section.reading_id)
        if reading is None:
            return

        section.status = SectionStatus.processing
        reading.status = ReadingStatus.processing
        db.commit()

        dest = section_audio_path(reading.id, section.index)
        loop = asyncio.get_running_loop()
        try:
            await loop.run_in_executor(
                _executor,
                generate_speech,
                section.text,
                reading.voice_id,
                reading.model_id,
                dest,
            )
            section.audio_path = str(dest)
            section.status = SectionStatus.ready
            section.error_message = None
        except Exception as exc:
            section.status = SectionStatus.failed
            section.error_message = str(exc)
            section.audio_path = None

        db.commit()
        db.refresh(reading)
        reading.status = compute_reading_status(list(reading.sections))
        db.commit()
    finally:
        db.close()


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        reading_id = await _queue.get()
        try:
            if reading_id in _active_readings:
                continue
            _active_readings.add(reading_id)

            db = SessionLocal()
            try:
                reading = db.get(Reading, reading_id)
                if reading is None:
                    continue
                section_ids = [
                    section.id
                    for section in reading.sections
                    if section.status in (SectionStatus.pending, SectionStatus.failed)
                ]
                reading.status = ReadingStatus.processing
                db.commit()
            finally:
                db.close()

            semaphore = asyncio.Semaphore(settings.worker_concurrency)

            async def run_one(sid: int) -> None:
                async with semaphore:
                    await _process_section(sid)

            await asyncio.gather(*(run_one(sid) for sid in section_ids))
        finally:
            _active_readings.discard(reading_id)
            _queue.task_done()


async def start_worker() -> None:
    global _queue, _worker_task
    if _queue is None:
        _queue = asyncio.Queue()
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop())


async def enqueue_reading(reading_id: int) -> None:
    if _queue is None:
        await start_worker()
    assert _queue is not None
    await _queue.put(reading_id)
