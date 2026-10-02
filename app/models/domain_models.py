import enum
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class ResearchStatus(str, enum.Enum):
    SCOUTING = "scouting"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    COMPLETED_BUT_CALLBACK_FAILED = "completed_but_callback_failed"
    BLOCKED = "blocked"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class Research(Base):
    __tablename__ = "research"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    theme: Mapped[str] = mapped_column(String(500))
    callback_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=ResearchStatus.SCOUTING.value, index=True)
    briefing_draft: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
    points: Mapped[list["ResearchPoint"]] = relationship(back_populates="research", cascade="all, delete-orphan")


class ResearchPoint(Base):
    __tablename__ = "research_points"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str] = mapped_column(Text)
    dependencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    is_parallelizable: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    audit: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    research: Mapped[Research] = relationship(back_populates="points")


class Evidence(Base):
    __tablename__ = "evidences"
    __table_args__ = (UniqueConstraint("research_point_id", "persona", "source_url", name="uq_evidence_source"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_point_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research_points.id", ondelete="CASCADE"), index=True)
    persona: Mapped[str] = mapped_column(String(24))
    source_url: Mapped[str] = mapped_column(Text)
    source_title: Mapped[str] = mapped_column(Text, default="")
    excerpt: Mapped[str] = mapped_column(Text)
    claim: Mapped[str] = mapped_column(Text)
    analysis: Mapped[str] = mapped_column(Text)
    accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __mapper_args__ = {"version_id_col": version}


class Event(Base):
    __tablename__ = "agent_event_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), index=True)
    persona: Mapped[str] = mapped_column(String(24))
    event_type: Mapped[str] = mapped_column(String(64))
    summary: Mapped[str] = mapped_column(String(500))
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), unique=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    citation_metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    audit_findings: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditTrail(Base):
    __tablename__ = "audit_trails"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    research_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("research.id", ondelete="CASCADE"), index=True)
    point_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("research_points.id", ondelete="CASCADE"), nullable=True)
    stage: Mapped[str] = mapped_column(String(32))
    attempt: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AppSettings(Base):
    __tablename__ = "app_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    encrypted_credentials: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    models: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    callback_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    openai_base_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, onupdate=now)
