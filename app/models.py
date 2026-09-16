from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class ReadingStatus(StrEnum):
    queued = "queued"
    processing = "processing"
    ready = "ready"
    partial = "partial"
    failed = "failed"


class SectionStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Reading(Base):
    __tablename__ = "readings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="Untitled reading")
    voice_id: Mapped[str] = mapped_column(String(64))
    model_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[ReadingStatus] = mapped_column(
        SAEnum(ReadingStatus), default=ReadingStatus.queued
    )
    source_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    sections: Mapped[list[Section]] = relationship(
        "Section",
        back_populates="reading",
        cascade="all, delete-orphan",
        order_by="Section.index",
    )


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reading_id: Mapped[int] = mapped_column(ForeignKey("readings.id"), index=True)
    index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[SectionStatus] = mapped_column(
        SAEnum(SectionStatus), default=SectionStatus.pending
    )
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    audio_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)

    reading: Mapped[Reading] = relationship("Reading", back_populates="sections")
