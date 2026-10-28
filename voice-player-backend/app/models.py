from datetime import datetime, timezone

from sqlalchemy import JSON, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Task(Base):
    """每个音频一条转写流水线任务记录。"""
    __tablename__ = "tasks"

    audio_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))  # processing | completed | failed
    progress: Mapped[int] = mapped_column(Integer, default=0)
    language: Mapped[str] = mapped_column(String(16), default="")
    error: Mapped[str] = mapped_column(Text, default="")
    generated_at: Mapped[datetime | None] = mapped_column(default=None)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Transcript(Base):
    __tablename__ = "transcripts"
    __table_args__ = (Index("ix_transcripts_audio", "audio_id", "start_time"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    audio_id: Mapped[str] = mapped_column(String(128))
    track_id: Mapped[str] = mapped_column(String(4))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Translation(Base):
    __tablename__ = "translations"
    __table_args__ = (Index("ix_translations_audio_lang", "audio_id", "language"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    audio_id: Mapped[str] = mapped_column(String(128))
    transcript_id: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(16))
    track_id: Mapped[str] = mapped_column(String(4))
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)
    text: Mapped[str] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)


class Analysis(Base):
    """大模型分析结果：kind = speakers | scenes，data 为接口返回体中对应部分。"""
    __tablename__ = "analyses"

    audio_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    kind: Mapped[str] = mapped_column(String(16), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    generated_at: Mapped[datetime] = mapped_column(default=utcnow)


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    data: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow)
