from __future__ import annotations

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.courses.models import Course


class Brochure(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "brochures"

    # No brochure metadata table exists in the verified production schema yet.
    # Keep this model importable without inventing a foreign key or touching
    # the database; a future approved metadata migration can use course_code.
    course_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    file_path: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped[Course] = relationship(
        "Course",
        primaryjoin=lambda: foreign(Brochure.course_code) == Course.code,
        lazy="joined",
        viewonly=True,
    )
