from pathlib import Path

import pytest

from app.config import settings
from app.services import tts


@pytest.mark.integration
def test_live_short_synthesis(tmp_path, monkeypatch, elevenlabs_test_api_key):
    monkeypatch.setattr(tts.settings, "elevenlabs_api_key", elevenlabs_test_api_key)
    monkeypatch.setattr(tts, "cache_audio_path", lambda key: tmp_path / f"{key}.mp3")

    destination = tmp_path / "live.mp3"
    result = tts.generate_speech(
        "Hello from the longform reader test suite.",
        settings.elevenlabs_voice_id,
        settings.elevenlabs_model_id,
        destination,
    )

    assert result == destination
    assert destination.exists()
    assert destination.stat().st_size > 0
    cache_files = list(Path(tmp_path).glob("*.mp3"))
    assert any(path.stat().st_size > 0 for path in cache_files)
