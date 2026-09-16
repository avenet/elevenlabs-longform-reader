from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "JBFqnCBsd6RMkjVDRZzb"
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    database_url: str = f"sqlite:///{BASE_DIR / 'data' / 'readings.db'}"
    media_root: str = str(BASE_DIR / "media" / "audio")
    section_target_chars: int = 3000
    section_max_chars: int = 3500
    worker_concurrency: int = 2
    request_timeout_seconds: float = 60.0
    max_attempts: int = 3
    backoff_base_seconds: float = 1.0
    backoff_max_seconds: float = 30.0
    max_upload_bytes: int = 5 * 1024 * 1024
    max_text_chars: int = 200_000
    max_sections: int = 200
    allowed_content_types: str = "text/plain,application/pdf"


settings = Settings()
