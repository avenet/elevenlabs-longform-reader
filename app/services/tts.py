import hashlib
import os
import re
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Protocol

from elevenlabs.client import ElevenLabs

from app.config import settings
from app.services.metrics import incr, log_event, timed
from app.services.storage import cache_audio_path

_cache_locks_guard = threading.Lock()
_cache_locks: dict[str, threading.Lock] = {}


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


def _lock_for_cache_key(cache_key: str) -> threading.Lock:
    with _cache_locks_guard:
        lock = _cache_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _cache_locks[cache_key] = lock
        return lock


def get_client(*, timeout: float | None = None) -> ElevenLabs:
    api_key = (settings.elevenlabs_api_key or "").strip()
    if not api_key or api_key == "your_api_key_here":
        raise RuntimeError("ELEVENLABS_API_KEY is not configured")
    return ElevenLabs(
        api_key=api_key,
        timeout=settings.request_timeout_seconds if timeout is None else timeout,
    )


def _copy_cached_audio(cached: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cached, destination)
    return destination


def _write_cache_atomically(cached: Path, audio_bytes: bytes) -> None:
    if not audio_bytes:
        raise RuntimeError("ElevenLabs returned empty audio")

    cached.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{cached.stem}.", suffix=".tmp", dir=cached.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(audio_bytes)
            handle.flush()
            os.fsync(handle.fileno())
        if temp_path.stat().st_size == 0:
            raise RuntimeError("ElevenLabs returned empty audio")
        os.replace(temp_path, cached)
    except Exception:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise


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
        incr("tts_cache_hits")
        log_event("tts_cache_hit", cache_key=cache_key, chars=len(text))
        return _copy_cached_audio(cached, destination)

    lock = _lock_for_cache_key(cache_key)
    with lock:
        if cached.exists() and cached.stat().st_size > 0:
            incr("tts_cache_hits")
            log_event("tts_cache_hit", cache_key=cache_key, chars=len(text))
            return _copy_cached_audio(cached, destination)

        active_client = client or get_client(timeout=timeout)
        incr("tts_cache_misses")
        with timed("elevenlabs_latency"):
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
        _write_cache_atomically(cached, audio_bytes)
        log_event(
            "tts_generated",
            cache_key=cache_key,
            chars=len(text),
            bytes=len(audio_bytes),
        )
        return _copy_cached_audio(cached, destination)


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
