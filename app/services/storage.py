from pathlib import Path

from app.config import BASE_DIR, settings


def ensure_storage() -> None:
    Path(settings.media_root).mkdir(parents=True, exist_ok=True)
    data_dir = BASE_DIR / "data"
    data_dir.mkdir(parents=True, exist_ok=True)


def reading_dir(reading_id: int) -> Path:
    path = Path(settings.media_root) / str(reading_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def section_audio_path(reading_id: int, index: int) -> Path:
    return reading_dir(reading_id) / f"{index}.mp3"


def cache_audio_path(cache_key: str) -> Path:
    cache_dir = Path(settings.media_root) / "_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / f"{cache_key}.mp3"
