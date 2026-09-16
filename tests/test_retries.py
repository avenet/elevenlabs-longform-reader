from datetime import UTC, datetime, timedelta

import httpx
import pytest
from elevenlabs.core.api_error import ApiError

from app.db import SessionLocal, run_migrations
from app.models import Reading, ReadingStatus, Section, SectionStatus
from app.services.errors import (
    CONFIG_ERROR_MESSAGE,
    FAILED_MESSAGE,
    RETRYING_MESSAGE,
    VOICE_UNAVAILABLE_MESSAGE,
    is_retryable,
    user_facing_error,
)
from app.services.worker import (
    _process_section,
    compute_backoff_seconds,
    section_due_for_processing,
)


def test_retryable_timeouts_and_rate_limits():
    assert is_retryable(TimeoutError("timed out"))
    assert is_retryable(ConnectionError("down"))
    assert is_retryable(httpx.ConnectError("boom"))
    assert is_retryable(ApiError(status_code=429, body="rate"))
    assert is_retryable(ApiError(status_code=503, body="upstream"))


def test_non_retryable_client_errors():
    assert not is_retryable(ApiError(status_code=401, body="bad key"))
    assert not is_retryable(ApiError(status_code=404, body="voice"))
    assert not is_retryable(ApiError(status_code=422, body="invalid"))
    assert not is_retryable(ApiError(status_code=400, body="bad request"))
    assert not is_retryable(RuntimeError("ELEVENLABS_API_KEY is not configured"))
    assert not is_retryable(RuntimeError("ElevenLabs returned empty audio"))


def test_user_facing_error_messages_are_safe():
    assert user_facing_error(TimeoutError(), retrying=True) == RETRYING_MESSAGE
    assert user_facing_error(ApiError(status_code=401)) == CONFIG_ERROR_MESSAGE
    assert user_facing_error(ApiError(status_code=404)) == VOICE_UNAVAILABLE_MESSAGE
    assert user_facing_error(ApiError(status_code=500)) == FAILED_MESSAGE
    assert "headers" not in user_facing_error(ApiError(status_code=500, body="secret"))


def test_backoff_increases_and_is_capped(monkeypatch):
    monkeypatch.setattr("app.services.worker.settings.backoff_base_seconds", 1.0)
    monkeypatch.setattr("app.services.worker.settings.backoff_max_seconds", 4.0)
    monkeypatch.setattr("app.services.worker.random.uniform", lambda a, b: 0.0)
    assert compute_backoff_seconds(1) == 1.0
    assert compute_backoff_seconds(2) == 2.0
    assert compute_backoff_seconds(3) == 4.0
    assert compute_backoff_seconds(4) == 4.0


def test_section_due_for_processing_respects_next_retry_at():
    pending = Section(
        reading_id=1,
        index=0,
        text="x",
        status=SectionStatus.pending,
        cache_key="k",
        next_retry_at=datetime.now(UTC) + timedelta(hours=1),
    )
    assert not section_due_for_processing(pending)

    pending.next_retry_at = datetime.now(UTC) - timedelta(seconds=1)
    assert section_due_for_processing(pending)


def _seed_section(text: str = "hello") -> tuple[int, int]:
    db = SessionLocal()
    try:
        reading = Reading(
            title="Retry reading",
            voice_id="voice-1",
            model_id="model-1",
            status=ReadingStatus.queued,
        )
        db.add(reading)
        db.flush()
        section = Section(
            reading_id=reading.id,
            index=0,
            text=text,
            status=SectionStatus.pending,
            cache_key="cache-key",
            char_count=len(text),
        )
        db.add(section)
        db.commit()
        return reading.id, section.id
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retryable_failure_then_success(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.worker.settings.max_attempts", 3)
    monkeypatch.setattr("app.services.worker.settings.backoff_base_seconds", 0.01)
    monkeypatch.setattr("app.services.worker.settings.backoff_max_seconds", 0.01)
    monkeypatch.setattr(
        "app.services.worker.section_audio_path",
        lambda reading_id, index: tmp_path / f"{reading_id}-{index}.mp3",
    )

    calls = {"n": 0}

    def flaky_generate(text, voice_id, model_id, destination):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("temporary")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"ok-audio")
        return destination

    monkeypatch.setattr("app.services.worker.generate_speech", flaky_generate)

    _, section_id = _seed_section()
    await _process_section(section_id)

    db = SessionLocal()
    try:
        section = db.get(Section, section_id)
        reading = db.get(Reading, section.reading_id)
        assert section.status == SectionStatus.ready
        assert section.attempt_count == 2
        assert section.error_message is None
        assert section.next_retry_at is None
        assert reading.status == ReadingStatus.ready
        assert calls["n"] == 2
    finally:
        db.close()


@pytest.mark.asyncio
async def test_permanent_failure_does_not_retry_forever(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.worker.settings.max_attempts", 3)
    monkeypatch.setattr(
        "app.services.worker.section_audio_path",
        lambda reading_id, index: tmp_path / f"{reading_id}-{index}.mp3",
    )

    calls = {"n": 0}

    def permanent_fail(*args, **kwargs):
        calls["n"] += 1
        raise ApiError(status_code=401, body="invalid api key secret")

    monkeypatch.setattr("app.services.worker.generate_speech", permanent_fail)

    _, section_id = _seed_section()
    await _process_section(section_id)

    db = SessionLocal()
    try:
        section = db.get(Section, section_id)
        assert section.status == SectionStatus.failed
        assert section.attempt_count == 1
        assert section.error_message == CONFIG_ERROR_MESSAGE
        assert "secret" not in (section.error_message or "")
        assert section.next_retry_at is None
        assert calls["n"] == 1
    finally:
        db.close()


@pytest.mark.asyncio
async def test_retryable_exhausts_max_attempts(monkeypatch, tmp_path):
    monkeypatch.setattr("app.services.worker.settings.max_attempts", 2)
    monkeypatch.setattr("app.services.worker.settings.backoff_base_seconds", 0.01)
    monkeypatch.setattr("app.services.worker.settings.backoff_max_seconds", 0.01)
    monkeypatch.setattr(
        "app.services.worker.section_audio_path",
        lambda reading_id, index: tmp_path / f"{reading_id}-{index}.mp3",
    )

    calls = {"n": 0}

    def always_fail(*args, **kwargs):
        calls["n"] += 1
        raise ApiError(status_code=503, body="upstream")

    monkeypatch.setattr("app.services.worker.generate_speech", always_fail)

    _, section_id = _seed_section()
    await _process_section(section_id)

    db = SessionLocal()
    try:
        section = db.get(Section, section_id)
        assert section.status == SectionStatus.failed
        assert section.attempt_count == 2
        assert section.error_message == FAILED_MESSAGE
        assert calls["n"] == 2
    finally:
        db.close()


def test_migration_adds_retry_columns(monkeypatch, tmp_path):
    from sqlalchemy import create_engine, text

    db_path = tmp_path / "migrate.db"
    url = f"sqlite:///{db_path}"
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE sections (
                    id INTEGER PRIMARY KEY,
                    reading_id INTEGER,
                    "index" INTEGER,
                    text TEXT,
                    status TEXT,
                    cache_key TEXT,
                    audio_path TEXT,
                    error_message TEXT,
                    char_count INTEGER
                )
                """
            )
        )

    monkeypatch.setattr("app.db.settings.database_url", url)
    monkeypatch.setattr("app.db.engine", engine)
    run_migrations()

    with engine.connect() as conn:
        columns = {row[1] for row in conn.execute(text("PRAGMA table_info(sections)"))}
    assert "attempt_count" in columns
    assert "next_retry_at" in columns
