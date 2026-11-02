from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Video(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "video"

    title: Mapped[str] = mapped_column(String(150), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    video_id: Mapped[str] = mapped_column(String(60), nullable=False)
    embed_url: Mapped[str] = mapped_column(String(500), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
