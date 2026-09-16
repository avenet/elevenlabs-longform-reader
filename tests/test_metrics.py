from unittest.mock import AsyncMock

from app.services import metrics, tts


def test_metrics_increment_on_generate(tmp_path, monkeypatch):
    metrics.reset()
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")

    class FakeTTS:
        def __init__(self):
            self.text_to_speech = self

        def convert(self, **kwargs):
            yield b"audio"

    destination = tmp_path / "out.mp3"
    tts.generate_speech("hello", "voice-1", "model-1", destination, client=FakeTTS())
    snap = metrics.snapshot()
    assert snap["tts_cache_misses"] == 1
    assert snap["elevenlabs_latency_count"] == 1

    tts.generate_speech("hello", "voice-1", "model-1", tmp_path / "out2.mp3", client=FakeTTS())
    snap = metrics.snapshot()
    assert snap["tts_cache_hits"] == 1


def test_metrics_endpoint_and_reading_counters(client, monkeypatch):
    metrics.reset()
    monkeypatch.setattr(
        "app.routers.readings.enqueue_reading",
        AsyncMock(return_value=None),
    )
    created = client.post(
        "/api/readings",
        data={"text": "Metrics reading body for counters."},
    )
    assert created.status_code == 201
    response = client.get("/api/metrics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["counters"]["readings_created"] == 1
    assert payload["counters"]["sections_queued"] >= 1
    assert payload["counters"]["characters_queued"] > 0
    assert "queue_depth" in payload
