import pytest

from app.db import SessionLocal
from app.models import Reading, SectionStatus
from app.services.worker import _process_section


class FakeTTS:
    calls = 0

    def __init__(self, *args, **kwargs):
        self.text_to_speech = self
        self.voices = self

    def convert(self, **kwargs):
        type(self).calls += 1
        yield b"fake-mp3-audio-bytes"

    def get_all(self):
        return type("Resp", (), {"voices": []})()


@pytest.fixture
def mock_elevenlabs(monkeypatch):
    FakeTTS.calls = 0
    monkeypatch.setattr("app.services.tts.get_client", lambda **kwargs: FakeTTS())
    monkeypatch.setattr("app.services.tts.ElevenLabs", FakeTTS)


@pytest.fixture
def sync_worker(monkeypatch):
    async def process_now(reading_id: int) -> None:
        db = SessionLocal()
        try:
            reading = db.get(Reading, reading_id)
            assert reading is not None
            section_ids = [
                section.id
                for section in reading.sections
                if section.status == SectionStatus.pending
            ]
        finally:
            db.close()
        for section_id in section_ids:
            await _process_section(section_id)

    monkeypatch.setattr("app.routers.readings.enqueue_reading", process_now)


def test_e2e_create_poll_and_stream_audio(client, mock_elevenlabs, sync_worker):
    created = client.post(
        "/api/readings",
        data={
            "title": "E2E reading",
            "text": "End to end chapter for progressive audio generation.",
        },
    )
    assert created.status_code == 201
    reading_id = created.json()["id"]

    ready = client.get(f"/api/readings/{reading_id}")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert payload["title"] == "E2E reading"
    assert payload["section_count"] >= 1
    assert all(section["status"] == "ready" for section in payload["sections"])

    audio = client.get(f"/api/readings/{reading_id}/sections/0/audio")
    assert audio.status_code == 200
    assert audio.headers["content-type"].startswith("audio/mpeg")
    assert audio.content == b"fake-mp3-audio-bytes"
    assert FakeTTS.calls >= 1


def test_e2e_cache_reuse_across_identical_readings(client, mock_elevenlabs, sync_worker):
    text = "Identical cache key body for reuse across readings."
    first = client.post("/api/readings", data={"text": text, "title": "First"})
    assert first.status_code == 201
    first_id = first.json()["id"]
    assert client.get(f"/api/readings/{first_id}").json()["status"] == "ready"
    calls_after_first = FakeTTS.calls
    assert calls_after_first >= 1

    second = client.post("/api/readings", data={"text": text, "title": "Second"})
    assert second.status_code == 201
    second_id = second.json()["id"]
    assert client.get(f"/api/readings/{second_id}").json()["status"] == "ready"
    assert FakeTTS.calls == calls_after_first

    audio = client.get(f"/api/readings/{second_id}/sections/0/audio")
    assert audio.status_code == 200
    assert audio.content == b"fake-mp3-audio-bytes"
