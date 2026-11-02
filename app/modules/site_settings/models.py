from __future__ import annotations

import uuid

from sqlalchemy import String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db_types import JSONText
from app.core.models import Base, TimestampMixin


class SiteSettings(TimestampMixin, Base):
    """A single row (id = 1) holding site-wide contact details."""

    __tablename__ = "site_setting"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(30))
    whatsapp: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(320))
    address: Mapped[str | None] = mapped_column(Text)
    google_form_url: Mapped[str | None] = mapped_column(String(500))
    social_links: Mapped[dict | str] = mapped_column(JSONText, nullable=False, default=dict)
