"""Database schema (3 tables).

candidates         one row per uploaded resume (raw text + structured profile)
screenings         one row per "analyze these resumes against this JD" run
screening_results  one row per (screening, candidate): score + evidence checks

Evidence is stored as JSONB so every decision can be audited later - this is
what makes hallucination checks and evaluation possible."""
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    name: Mapped[Optional[str]] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(64))
    # Full resume text. Evidence quotes are searched in THIS text, so they are
    # verbatim and can never be invented by the LLM.
    raw_text: Mapped[str] = mapped_column(Text)
    # LLM-extracted structure: skills, experience[], education[], experience_years
    profile: Mapped[dict] = mapped_column(JSONB, default=dict)
    parse_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|parsed|failed
    parse_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Screening(Base):
    __tablename__ = "screenings"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    hr_request: Mapped[str] = mapped_column(Text)
    jd_text: Mapped[str] = mapped_column(Text, default="")
    requirements: Mapped[dict] = mapped_column(JSONB, default=dict)  # structured JD
    # running -> awaiting_approval -> approved   (or needs_input / failed)
    status: Mapped[str] = mapped_column(String(30), default="running")
    trace: Mapped[list] = mapped_column(JSONB, default=list)  # the agent's step log
    summary: Mapped[Optional[str]] = mapped_column(Text)
    error: Mapped[Optional[str]] = mapped_column(Text)
    excel_path: Mapped[Optional[str]] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    results: Mapped[list["ScreeningResult"]] = relationship(
        back_populates="screening", cascade="all, delete-orphan", order_by="ScreeningResult.rank"
    )


class ScreeningResult(Base):
    __tablename__ = "screening_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    screening_id: Mapped[int] = mapped_column(ForeignKey("screenings.id", ondelete="CASCADE"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer)
    score: Mapped[float] = mapped_column(Float)
    meets_all_required: Mapped[bool] = mapped_column(Boolean, default=False)
    shortlisted: Mapped[bool] = mapped_column(Boolean, default=False)  # final decision (HR can flip it)
    overridden: Mapped[bool] = mapped_column(Boolean, default=False)   # True once HR changed it
    experience_years: Mapped[Optional[float]] = mapped_column(Float)
    checks: Mapped[list] = mapped_column(JSONB, default=list)          # requirement-by-requirement evidence

    screening: Mapped[Screening] = relationship(back_populates="results")
    candidate: Mapped[Candidate] = relationship()
