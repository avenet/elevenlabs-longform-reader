import asyncio
import random
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.models import Reading, ReadingStatus, Section, SectionStatus, utcnow
from app.services.errors import is_retryable, user_facing_error
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
        if SectionStatus.processing in statuses:
            return ReadingStatus.processing
        return ReadingStatus.queued
    return ReadingStatus.partial


def compute_backoff_seconds(attempt: int) -> float:
    exponent = max(attempt - 1, 0)
    base = settings.backoff_base_seconds * (2**exponent)
    capped = min(base, settings.backoff_max_seconds)
    jitter = random.uniform(0, capped * 0.25)
    return capped + jitter


def section_due_for_processing(section: Section, *, now=None) -> bool:
    if section.status != SectionStatus.pending:
        return False
    current = now or utcnow()
    if section.next_retry_at is None:
        return True
    retry_at = section.next_retry_at
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=current.tzinfo)
    return retry_at <= current


async def _process_section(section_id: int) -> None:
    db: Session = SessionLocal()
    try:
        section = db.get(Section, section_id)
        if section is None:
            return

        reading = db.get(Reading, section.reading_id)
        if reading is None:
            return

        dest = section_audio_path(reading.id, section.index)
        loop = asyncio.get_running_loop()

        while True:
            section.status = SectionStatus.processing
            reading.status = ReadingStatus.processing
            section.attempt_count += 1
            section.next_retry_at = None
            db.commit()

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
                section.next_retry_at = None
                db.commit()
                break
            except Exception as exc:
                retryable = is_retryable(exc)
                attempts_left = section.attempt_count < settings.max_attempts
                if retryable and attempts_left:
                    delay = compute_backoff_seconds(section.attempt_count)
                    section.error_message = user_facing_error(exc, retrying=True)
                    section.audio_path = None
                    section.status = SectionStatus.pending
                    section.next_retry_at = utcnow() + timedelta(seconds=delay)
                    db.commit()
                    await asyncio.sleep(delay)
                    db.refresh(section)
                    db.refresh(reading)
                    continue

                section.status = SectionStatus.failed
                section.error_message = user_facing_error(exc, retrying=False)
                section.audio_path = None
                section.next_retry_at = None
                db.commit()
                break

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
                now = utcnow()
                section_ids = [
                    section.id
                    for section in reading.sections
                    if section_due_for_processing(section, now=now)
                ]
                reading.status = ReadingStatus.processing
                db.commit()
            finally:
                db.close()

            semaphore = asyncio.Semaphore(settings.worker_concurrency)

            async def run_one(sid: int, limiter: asyncio.Semaphore = semaphore) -> None:
                async with limiter:
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
