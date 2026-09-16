from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.db import SessionLocal
from app.models import Reading, ReadingStatus, Section, SectionStatus
from app.services.worker import recover_pending


def _seed_reading(*, section_status: SectionStatus, next_retry_at=None) -> int:
    db = SessionLocal()
    try:
        reading = Reading(
            title="Recovery reading",
            voice_id="voice-1",
            model_id="model-1",
            status=ReadingStatus.processing,
        )
        db.add(reading)
        db.flush()
        db.add(
            Section(
                reading_id=reading.id,
                index=0,
                text="Unfinished section text.",
                status=section_status,
                cache_key="recovery-key",
                char_count=24,
                next_retry_at=next_retry_at,
            )
        )
        db.commit()
        return reading.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recover_pending_reenqueues_pending_sections(monkeypatch):
    reading_id = _seed_reading(section_status=SectionStatus.pending)
    enqueue = AsyncMock()
    monkeypatch.setattr("app.services.worker.enqueue_reading", enqueue)

    enqueued = await recover_pending()

    assert enqueued == [reading_id]
    enqueue.assert_awaited_once_with(reading_id)


@pytest.mark.asyncio
async def test_recover_pending_resets_processing_then_reenqueues(monkeypatch):
    reading_id = _seed_reading(section_status=SectionStatus.processing)
    enqueue = AsyncMock()
    monkeypatch.setattr("app.services.worker.enqueue_reading", enqueue)

    enqueued = await recover_pending()

    assert enqueued == [reading_id]
    enqueue.assert_awaited_once_with(reading_id)

    db = SessionLocal()
    try:
        section = db.query(Section).filter(Section.reading_id == reading_id).one()
        assert section.status == SectionStatus.pending
        assert section.next_retry_at is None
    finally:
        db.close()


@pytest.mark.asyncio
async def test_recover_pending_skips_ready_readings(monkeypatch):
    reading_id = _seed_reading(section_status=SectionStatus.ready)
    enqueue = AsyncMock()
    monkeypatch.setattr("app.services.worker.enqueue_reading", enqueue)

    enqueued = await recover_pending()

    assert enqueued == []
    enqueue.assert_not_awaited()
    assert reading_id is not None


@pytest.mark.asyncio
async def test_recover_pending_schedules_future_retry(monkeypatch):
    future = datetime.now(UTC) + timedelta(hours=1)
    reading_id = _seed_reading(
        section_status=SectionStatus.pending,
        next_retry_at=future,
    )
    enqueue = AsyncMock()
    scheduled: list = []

    def fake_create_task(coro):
        scheduled.append(coro)
        coro.close()
        return object()

    monkeypatch.setattr("app.services.worker.enqueue_reading", enqueue)
    monkeypatch.setattr("app.services.worker.asyncio.create_task", fake_create_task)

    enqueued = await recover_pending()

    assert enqueued == []
    enqueue.assert_not_awaited()
    assert len(scheduled) == 1
    assert reading_id is not None
