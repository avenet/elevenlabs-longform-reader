import hashlib
import re
import shutil
from pathlib import Path
from typing import Protocol

from elevenlabs.client import ElevenLabs

from app.config import settings
from app.services.storage import cache_audio_path


class TTSClient(Protocol):
    @property
    def text_to_speech(self): ...

    @property
    def voices(self): ...


def normalize_for_cache(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_cache_key(voice_id: str, model_id: str, text: str) -> str:
    payload = f"{voice_id}|{model_id}|{normalize_for_cache(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_client(*, timeout: float | None = None) -> ElevenLabs:
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    return ElevenLabs(
        api_key=api_key,
        timeout=settings.request_timeout_seconds if timeout is None else timeout,
    )


def generate_speech(
    text: str,
    voice_id: str,
    model_id: str,
    destination: Path,
    *,
    client: TTSClient | None = None,
    timeout: float | None = None,
) -> Path:
    cache_key = build_cache_key(voice_id, model_id, text)
    cached = cache_audio_path(cache_key)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if cached.exists() and cached.stat().st_size > 0:
        shutil.copyfile(cached, destination)
        return destination

    active_client = client or get_client(timeout=timeout)
    audio_iter = active_client.text_to_speech.convert(
        voice_id=voice_id,
        text=text,
        model_id=model_id,
        output_format="mp3_44100_128",
    )

    chunks: list[bytes] = []
    for chunk in audio_iter:
        if isinstance(chunk, bytes):
            chunks.append(chunk)

    audio_bytes = b"".join(chunks)
    if not audio_bytes:
        raise RuntimeError("ElevenLabs returned empty audio")

    cached.write_bytes(audio_bytes)
    shutil.copyfile(cached, destination)
    return destination


def list_voices(*, client: TTSClient | None = None) -> list[dict]:
    active_client = client or get_client()
    response = active_client.voices.get_all()
    voices = []
    for voice in response.voices or []:
        voices.append(
            {
                "voice_id": voice.voice_id,
                "name": voice.name or voice.voice_id,
                "preview_url": getattr(voice, "preview_url", None),
            }
        )
    return voices
