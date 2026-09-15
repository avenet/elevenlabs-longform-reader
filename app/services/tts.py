import hashlib
import os
import re
import shutil
from pathlib import Path

from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs

from app.config import BASE_DIR, settings
from app.services.storage import cache_audio_path


def normalize_for_cache(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def build_cache_key(voice_id: str, model_id: str, text: str) -> str:
    payload = f"{voice_id}|{model_id}|{normalize_for_cache(text)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _api_key() -> str:
    load_dotenv(BASE_DIR / ".env", override=True)
    return (os.getenv("ELEVENLABS_API_KEY") or settings.elevenlabs_api_key or "").strip()


def get_client() -> ElevenLabs:
    api_key = _api_key()
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    return ElevenLabs(api_key=api_key)


def generate_speech(text: str, voice_id: str, model_id: str, destination: Path) -> Path:
    cache_key = build_cache_key(voice_id, model_id, text)
    cached = cache_audio_path(cache_key)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if cached.exists() and cached.stat().st_size > 0:
        shutil.copyfile(cached, destination)
        return destination

    client = get_client()
    audio_iter = client.text_to_speech.convert(
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


def list_voices() -> list[dict]:
    client = get_client()
    response = client.voices.get_all()
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
