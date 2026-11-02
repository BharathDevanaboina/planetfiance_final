"""SQLAlchemy models reconstructed from the supplied screenshots.

The screenshots show definitions through ExamOption. Additional fields or classes
may exist beyond the visible area of the original file.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.db_types import JSONText
from app.core.models import Base, UUIDPrimaryKeyMixin


class ExamSet(Base):
    """One of the three question sets. Sets are never edited: delete one and upload a new one."""

    __tablename__ = "exam_set"

    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    question_count: Mapped[int] = mapped_column(Integer, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(320), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def id(self) -> uuid.UUID:
        """Stable API-only identifier; ``slot`` remains the database key."""
        return uuid.uuid5(uuid.NAMESPACE_URL, f"planetfiance/exam-set/{self.slot}")


class ExamPassage(UUIDPrimaryKeyMixin, Base):
    """A reading passage shared by several questions (kept together when shuffling)."""

    __tablename__ = "exam_passage"

    exam_set_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    passage_key: Mapped[str] = mapped_column(String(50), nullable=False)
    section: Mapped[str] = mapped_column(String(1), nullable=False)
    content: Mapped[list | str] = mapped_column(JSONText, nullable=False)


class ExamQuestion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exam_question"

    exam_set_slot: Mapped[int] = mapped_column(Integer, nullable=False)
    passage_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # row order in uploaded file
    section: Mapped[str] = mapped_column(String(1), nullable=False)
    subsection: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[list | str] = mapped_column(JSONText, nullable=False)
    options: Mapped[list[ExamOption]] = relationship(
        "ExamOption",
        primaryjoin=lambda: ExamQuestion.id == foreign(ExamOption.question_id),
        order_by="ExamOption.label",
        lazy="selectin",
        viewonly=True,
    )


class ExamOption(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "exam_option"

    question_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    label: Mapped[str] = mapped_column(String(1), nullable=False)  # A-D as in Excel
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
