from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, SmallInteger, String, text, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AdminUser(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """The sole person allowed into the admin portal.

    Passwords and Firebase-user lifecycle remain in Firebase Authentication.
    ``singleton_key`` is deliberately fixed to one and unique: PostgreSQL can
    therefore never contain more than one administrator allow-list record.
    """

    __tablename__ = "admin_users"
    __table_args__ = (CheckConstraint("singleton_key = 1", name="singleton_key_one"),)

    singleton_key: Mapped[int] = mapped_column(
        SmallInteger, unique=True, nullable=False, default=1, server_default=text("1")
    )
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=true())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
