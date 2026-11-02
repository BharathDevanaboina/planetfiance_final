from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Announcement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "announcement"

    message: Mapped[str] = mapped_column(String(500), nullable=False)
    link_url: Mapped[str | None] = mapped_column(String(500))
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
