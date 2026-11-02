"""Local-only database setup for operating the admin dashboard safely.

This module is intentionally called only when ``LOCAL_DASHBOARD_MODE=true``.
It creates a separate SQLite schema with just the tables used by the currently
available dashboard sections, then seeds it once with disposable sample data.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - register mapped tables before selecting them
from app.core.config import Settings
from app.core.models import Base
from app.modules.admin_auth.models import AdminUser
from app.modules.announcements.models import Announcement
from app.modules.banners.models import Banner
from app.modules.batches.models import Batch
from app.modules.courses.models import Course
from app.modules.exam.models import ExamOption, ExamPassage, ExamQuestion, ExamSet
from app.modules.site_settings.models import SiteSettings
from app.modules.videos.models import Video

LOCAL_ADMIN_UID = "local-dashboard-admin"
LOCAL_ADMIN_EMAIL = "local-admin@example.com"

ACTIVE_LOCAL_TABLES = (
    AdminUser.__table__,
    Course.__table__,
    Batch.__table__,
    Banner.__table__,
    Announcement.__table__,
    SiteSettings.__table__,
    Video.__table__,
    ExamSet.__table__,
    ExamPassage.__table__,
    ExamQuestion.__table__,
    ExamOption.__table__,
)


def initialize_local_dashboard(settings: Settings, *, include_local_admin: bool) -> None:
    """Create and seed a disposable local dashboard database once.

    Firebase-auth test mode intentionally starts without an allow-list record.
    The operator must use the existing CLI to register an existing Firebase user
    into that separate SQLite database.
    """
    engine = create_engine(settings.sqlalchemy_url, future=True)
    Base.metadata.create_all(engine, tables=list(ACTIVE_LOCAL_TABLES))
    with Session(engine) as db:
        if db.scalar(select(Course.code).limit(1)) is not None:
            return
        _seed(db, include_local_admin=include_local_admin)


def _seed(db: Session, *, include_local_admin: bool) -> None:
    """Seed only a new local database; never overwrite a user's local work."""
    if include_local_admin:
        db.add(
            AdminUser(
                firebase_uid=LOCAL_ADMIN_UID,
                email=LOCAL_ADMIN_EMAIL,
                full_name="Local dashboard administrator",
            )
        )
    db.add_all(
        [
            Course(
                code="IBFAP",
                name="IBFAP",
                duration_text="3 years",
                summary="Integrated banking, finance and accounting programme.",
                eligibility="12th standard or equivalent",
                total_fee_inr=180000,
                fee_note="Installments available.",
                fee_breakup=[
                    {"label": "Year 1", "amount_inr": 60000},
                    {"label": "Year 2", "amount_inr": 60000},
                    {"label": "Year 3", "amount_inr": 60000},
                ],
                display_order=1,
                is_active=True,
            ),
            Course(
                code="ADV_BCOM",
                name="Advance B.Com.",
                duration_text="3 years",
                summary="Commerce degree with professional-skills support.",
                eligibility="12th standard or equivalent",
                total_fee_inr=150000,
                fee_note=None,
                fee_breakup=[
                    {"label": "Year 1", "amount_inr": 50000},
                    {"label": "Year 2", "amount_inr": 50000},
                    {"label": "Year 3", "amount_inr": 50000},
                ],
                display_order=2,
                is_active=True,
            ),
            Course(
                code="PGDM",
                name="PGDM",
                duration_text="2 years",
                summary="Postgraduate diploma in management.",
                eligibility="Graduation",
                total_fee_inr=220000,
                fee_note="Subject to admission criteria.",
                fee_breakup=[
                    {"label": "Year 1", "amount_inr": 110000},
                    {"label": "Year 2", "amount_inr": 110000},
                ],
                display_order=3,
                is_active=True,
            ),
        ]
    )
    today = date.today()
    db.add_all(
        [
            Batch(
                course_code="IBFAP",
                start_date=today - timedelta(days=20),
                end_date=today + timedelta(days=320),
                timings="10:00 AM – 1:00 PM",
                mode="offline",
                is_active=True,
            ),
            Batch(
                course_code="PGDM",
                start_date=today + timedelta(days=30),
                end_date=today + timedelta(days=760),
                timings="6:00 PM – 8:30 PM",
                mode="online",
                is_active=True,
            ),
        ]
    )
    db.add(
        SiteSettings(
            id=uuid.uuid4(),
            phone="+91 98765 43210",
            whatsapp="+91 98765 43210",
            email="admissions@example.com",
            address="PlanetFiance College, Hyderabad",
            google_form_url="https://forms.google.com/",
            social_links={
                "facebook": "https://facebook.com/",
                "instagram": "https://instagram.com/",
                "youtube": "https://youtube.com/",
                "linkedin": "https://linkedin.com/",
            },
        )
    )
    db.add(
        Announcement(
            message="Local development data: admissions are open.",
            link_url="https://forms.google.com/",
            display_order=1,
            is_active=True,
        )
    )
    db.add(
        Video(
            title="PlanetFiance campus introduction",
            url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            platform="youtube",
            video_id="dQw4w9WgXcQ",
            embed_url="https://www.youtube.com/embed/dQw4w9WgXcQ",
            display_order=1,
            is_active=True,
        )
    )
    db.commit()
