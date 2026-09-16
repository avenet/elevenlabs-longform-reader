from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models import ReadingStatus, SectionStatus


class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    index: int
    status: SectionStatus
    char_count: int
    error_message: str | None = None
    preview: str | None = None


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    voice_id: str
    model_id: str
    status: ReadingStatus
    source_filename: str | None = None
    created_at: datetime
    updated_at: datetime
    sections: list[SectionOut]
    section_count: int = 0
    total_char_count: int = 0


class VoiceOut(BaseModel):
    voice_id: str
    name: str
    preview_url: str | None = None
