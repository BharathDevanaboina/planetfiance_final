from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.timeutil import utc_now
from app.modules.admin_auth.models import AdminUser


def get_active_admin(db: Session, firebase_uid: str, email: str) -> AdminUser | None:
    """Return an active admin only when immutable UID and verified email match."""
    normalized_email = email.strip().lower()
    if not normalized_email or not firebase_uid:
        return None

    return db.scalar(
        select(AdminUser).where(
            AdminUser.firebase_uid == firebase_uid,
            AdminUser.email == normalized_email,
            AdminUser.is_active.is_(True),
        )
    )


def record_login(db: Session, admin: AdminUser) -> None:
    """Record a login, updating the timestamp at most once per hour."""
    now = utc_now()
    last = admin.last_login_at

    # SQLite may return a naive datetime even when timezone=True.
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=now.tzinfo)

    if last is None or now - last > timedelta(hours=1):
        admin.last_login_at = now
        db.commit()


def initialize_admin(
    db: Session,
    firebase_uid: str,
    email: str,
    full_name: str | None = None,
) -> AdminUser:
    """Create the one allowed administrator exactly once.

    The database's unique singleton key is the final concurrency guard.  The
    explicit query gives operators a clear, fail-closed message on later runs.
    """
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("Email must not be empty.")

    if not firebase_uid:
        raise ValueError("Firebase UID must not be empty.")

    if db.scalar(select(AdminUser.id).limit(1)) is not None:
        raise ValueError("The sole administrator is already registered; additional admins are not permitted.")

    admin = AdminUser(firebase_uid=firebase_uid, email=normalized_email, full_name=full_name)
    db.add(admin)
    db.commit()
    return admin


def list_admins(db: Session) -> list[AdminUser]:
    """Return all admins ordered by email."""
    return list(db.scalars(select(AdminUser).order_by(AdminUser.email)))
