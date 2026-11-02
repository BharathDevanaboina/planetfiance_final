from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.site_settings.models import SiteSettings
from app.modules.site_settings.schemas import (
    SiteSettingsOut,
    SiteSettingsUpdate,
    SocialLinks,
)


def _get_existing(db: Session) -> SiteSettings:
    """The production table uses a UUID key and already owns its single row."""
    row = db.scalar(select(SiteSettings).order_by(SiteSettings.created_at).limit(1))
    if row is None:
        raise RuntimeError("The existing site_setting table has no settings row.")
    return row


def to_out(row: SiteSettings) -> SiteSettingsOut:
    return SiteSettingsOut(
        phone=row.phone,
        whatsapp=row.whatsapp,
        email=row.email,
        address=row.address,
        google_form_url=row.google_form_url,
        social_links=SocialLinks(**(row.social_links if isinstance(row.social_links, dict) else {})),
    )


def get_settings_out(db: Session) -> SiteSettingsOut:
    return to_out(_get_existing(db))


def update_settings(
    db: Session,
    data: SiteSettingsUpdate,
) -> SiteSettingsOut:
    row = _get_existing(db)
    row.phone = data.phone
    row.whatsapp = data.whatsapp
    row.email = str(data.email) if data.email else None
    row.address = data.address
    row.google_form_url = data.google_form_url
    row.social_links = data.social_links.model_dump(exclude_none=True)
    db.commit()
    return to_out(row)
