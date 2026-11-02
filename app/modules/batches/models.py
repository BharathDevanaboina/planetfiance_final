from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, Date, String, Text, true
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.courses.models import Course


class Batch(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "batch"

    course_code: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    timings: Mapped[str] = mapped_column(String(100), nullable=False)
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="online", server_default="true")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())

    course: Mapped[Course] = relationship(
        "Course",
        primaryjoin=lambda: foreign(Batch.course_code) == Course.code,
        lazy="joined",
        viewonly=True,
    )
