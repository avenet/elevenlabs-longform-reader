import pytest

from app.config import Settings
from app.services import tts


def test_settings_env_var_beats_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ELEVENLABS_API_KEY=from-file\nREQUEST_TIMEOUT_SECONDS=10\n")
    monkeypatch.setenv("ELEVENLABS_API_KEY", "from-env")
    monkeypatch.setenv("REQUEST_TIMEOUT_SECONDS", "99")

    loaded = Settings(_env_file=str(env_file))

    assert loaded.elevenlabs_api_key == "from-env"
    assert loaded.request_timeout_seconds == 99.0


def test_settings_reads_env_file_when_env_unset(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("ELEVENLABS_API_KEY=from-file\nMAX_ATTEMPTS=5\n")
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
    monkeypatch.delenv("MAX_ATTEMPTS", raising=False)

    loaded = Settings(_env_file=str(env_file))

    assert loaded.elevenlabs_api_key == "from-file"
    assert loaded.max_attempts == 5


def test_get_client_raises_when_key_missing(monkeypatch):
    monkeypatch.setattr(tts.settings, "elevenlabs_api_key", "")
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY is not configured"):
        tts.get_client()


def test_get_client_raises_when_key_is_placeholder(monkeypatch):
    monkeypatch.setattr(tts.settings, "elevenlabs_api_key", "your_api_key_here")
    with pytest.raises(RuntimeError, match="ELEVENLABS_API_KEY is not configured"):
        tts.get_client()


def test_generate_speech_uses_injected_client(tmp_path, monkeypatch):
    class FakeTTS:
        def __init__(self):
            self.calls = 0
            self.text_to_speech = self
            self.voices = self

        def convert(self, **kwargs):
            self.calls += 1
            yield b"audio-bytes"

        def get_all(self):
            return type("Resp", (), {"voices": []})()

    fake = FakeTTS()
    destination = tmp_path / "out.mp3"
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")

    result = tts.generate_speech(
        "hello world",
        "voice-1",
        "model-1",
        destination,
        client=fake,
    )

    assert result == destination
    assert destination.read_bytes() == b"audio-bytes"
    assert fake.calls == 1


def test_generate_speech_cache_hit_skips_client(tmp_path, monkeypatch):
    class FakeTTS:
        def __init__(self):
            self.calls = 0
            self.text_to_speech = self

        def convert(self, **kwargs):
            self.calls += 1
            yield b"should-not-run"

    cache_key = tts.build_cache_key("voice-1", "model-1", "hello")
    cached = tmp_path / f"{cache_key}.mp3"
    cached.write_bytes(b"cached-audio")
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")

    fake = FakeTTS()
    destination = tmp_path / "out.mp3"
    result = tts.generate_speech(
        "hello",
        "voice-1",
        "model-1",
        destination,
        client=fake,
    )

    assert result == destination
    assert destination.read_bytes() == b"cached-audio"
    assert fake.calls == 0
