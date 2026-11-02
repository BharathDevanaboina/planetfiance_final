from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, foreign, mapped_column, relationship

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.modules.courses.models import Course


class Banner(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "banner"

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    # When set, clicking the banner opens the course registration form and then
    # downloads that course's brochure. When empty, the banner is informational.
    course_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_path: Mapped[str] = mapped_column(String(300), nullable=False)
    image_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumb_path: Mapped[str] = mapped_column(String(300), nullable=False)
    thumb_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    image_width: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_height: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    course = relationship(
        "Course",
        primaryjoin=lambda: foreign(Banner.course_code) == Course.code,
        lazy="joined",
        viewonly=True,
    )
