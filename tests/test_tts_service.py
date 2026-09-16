import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.services import tts


class FakeTTS:
    def __init__(self, chunks: list[bytes] | None = None, *, delay: float = 0.0):
        self.calls = 0
        self.chunks = chunks if chunks is not None else [b"audio-bytes"]
        self.delay = delay
        self.text_to_speech = self
        self.voices = self
        self._lock = threading.Lock()

    def convert(self, **kwargs):
        with self._lock:
            self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        yield from self.chunks

    def get_all(self):
        return type("Resp", (), {"voices": []})()


def test_cache_hit_does_not_call_elevenlabs(tmp_path, monkeypatch):
    cache_key = tts.build_cache_key("voice-1", "model-1", "hello")
    cached = tmp_path / f"{cache_key}.mp3"
    cached.write_bytes(b"cached-audio")
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")

    fake = FakeTTS()
    destination = tmp_path / "out.mp3"
    result = tts.generate_speech("hello", "voice-1", "model-1", destination, client=fake)

    assert result == destination
    assert destination.read_bytes() == b"cached-audio"
    assert fake.calls == 0


def test_empty_returned_audio_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")
    fake = FakeTTS(chunks=[])
    destination = tmp_path / "out.mp3"

    with pytest.raises(RuntimeError, match="empty audio"):
        tts.generate_speech("hello", "voice-1", "model-1", destination, client=fake)

    assert not destination.exists()
    assert list(tmp_path.glob("*.mp3")) == []
    assert list(tmp_path.glob("*.tmp")) == []


def test_successful_audio_written_to_cache_and_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / "cache" / f"{key}.mp3")
    (tmp_path / "cache").mkdir()
    fake = FakeTTS(chunks=[b"abc", b"def"])
    destination = tmp_path / "reading" / "0.mp3"

    result = tts.generate_speech("hello", "voice-1", "model-1", destination, client=fake)

    assert result == destination
    assert destination.read_bytes() == b"abcdef"
    cache_key = tts.build_cache_key("voice-1", "model-1", "hello")
    cached = Path(tmp_path / "cache" / f"{cache_key}.mp3")
    assert cached.read_bytes() == b"abcdef"
    assert fake.calls == 1
    assert list((tmp_path / "cache").glob("*.tmp")) == []


def test_concurrent_identical_requests_single_upstream_call(tmp_path, monkeypatch):
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / "cache" / f"{key}.mp3")
    (tmp_path / "cache").mkdir()
    fake = FakeTTS(chunks=[b"shared-audio"], delay=0.05)

    def run(index: int) -> Path:
        destination = tmp_path / "out" / f"{index}.mp3"
        return tts.generate_speech(
            "same text",
            "voice-1",
            "model-1",
            destination,
            client=fake,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, range(2)))

    assert fake.calls == 1
    assert all(path.exists() and path.read_bytes() == b"shared-audio" for path in results)
    cache_key = tts.build_cache_key("voice-1", "model-1", "same text")
    cached = tmp_path / "cache" / f"{cache_key}.mp3"
    assert cached.read_bytes() == b"shared-audio"
    assert list((tmp_path / "cache").glob("*.tmp")) == []
