from pathlib import Path

import pytest

from app.services import tts


class FakeTTS:
    def __init__(self, chunks: list[bytes] | None = None):
        self.calls = 0
        self.chunks = chunks if chunks is not None else [b"audio-bytes"]
        self.text_to_speech = self
        self.voices = self

    def convert(self, **kwargs):
        self.calls += 1
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
    assert not any(tmp_path.glob("*.mp3"))


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
