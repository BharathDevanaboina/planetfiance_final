from __future__ import annotations

import io

import pytest
from openpyxl import Workbook
from PIL import Image
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_engine, get_session_factory
from app.core.dependencies import _identity, _sheets, _storage
from app.core.error import ValidationFailed
from app.core.identity import FakeIdentityVerifier
from app.core.local_development import initialize_local_dashboard
from app.core.storage import LocalStorage
from app.modules.admin_auth.dependencies import require_admin
from app.modules.announcements import service as announcements
from app.modules.announcements.schemas import AnnouncementIn
from app.modules.banners import service as banners
from app.modules.batches import service as batches
from app.modules.batches.schemas import BatchCreate, BatchUpdate
from app.modules.courses import service as courses
from app.modules.courses.schemas import CourseUpdate
from app.modules.exam import service as exam
from app.modules.exam.template import QUESTION_HEADER
from app.modules.site_settings import service as site_settings
from app.modules.site_settings.schemas import SiteSettingsUpdate, SocialLinks
from app.modules.videos import service as videos
from app.modules.videos.schemas import VideoIn


def _reset_runtime_caches() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    _identity.cache_clear()
    _sheets.cache_clear()
    _storage.cache_clear()


def _question_set_bytes(prefix: str) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "questions"
    sheet.append(QUESTION_HEADER)
    index = 0
    for section, count, subsection in (
        ("A", 75, "Problem Solving"),
        ("B", 75, "Arithmetical Ability"),
        ("C", 50, "Vocabulary"),
    ):
        for _ in range(count):
            index += 1
            sheet.append(
                [
                    section,
                    subsection,
                    "",
                    f"{prefix} question {index}",
                    f"{prefix} answer A {index}",
                    f"{prefix} answer B {index}",
                    f"{prefix} answer C {index}",
                    f"{prefix} answer D {index}",
                    "A",
                ]
            )
    output = io.BytesIO()
    workbook.save(output)
    return output.getvalue()


def _png_bytes() -> bytes:
    image = Image.new("RGB", (80, 40), "green")
    output = io.BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def test_local_dashboard_mode_uses_disposable_sqlite_and_real_admin_crud(
    tmp_path, monkeypatch
) -> None:
    database = tmp_path / "planetfiance-local.db"
    storage_dir = tmp_path / "storage"
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LOCAL_DASHBOARD_MODE", "true")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database.as_posix()}")
    monkeypatch.setenv("AUTH_MODE", "fake")
    monkeypatch.setenv("APP_CHECK_ENABLED", "false")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(storage_dir))
    monkeypatch.setenv("PUBLIC_BASE_URL", "http://testserver")
    monkeypatch.setenv("SHEETS_BACKEND", "fake")
    monkeypatch.setenv("FAKE_SHEETS_DIR", str(tmp_path / "sheets"))
    monkeypatch.setenv("INTERNAL_AUTH_MODE", "token")
    monkeypatch.setenv("INTERNAL_TASK_TOKEN", "local-internal-token-change-me-0123456789")
    _reset_runtime_caches()

    settings = get_settings()
    initialize_local_dashboard(settings, include_local_admin=True)
    engine = get_engine()
    assert {"brochure", "gallery_image", "pending_sheet_row"}.isdisjoint(inspect(engine).get_table_names())

    with Session(engine) as db:
        principal = require_admin(db=db, verifier=FakeIdentityVerifier())
        assert principal.email == "local-admin@example.com"
        assert len(courses.list_courses(db)) == 3

        assert courses.update_course(
            db,
            "IBFAP",
            CourseUpdate(
                total_fee_inr=181000,
                fee_breakup=[
                    {"label": "Year 1", "amount_inr": 60000},
                    {"label": "Year 2", "amount_inr": 60000},
                    {"label": "Year 3", "amount_inr": 61000},
                ],
            ),
        ).total_fee_inr == 181000
        assert site_settings.update_settings(
            db,
            SiteSettingsUpdate(
                phone="+919876543211",
                whatsapp="+919876543211",
                email="local-admin@example.com",
                address="Updated local address",
                google_form_url="https://forms.google.com/",
                social_links=SocialLinks(),
            ),
        ).address == "Updated local address"
        batch = batches.create_batch(
            db,
            BatchCreate(
                course_code="IBFAP",
                start_date="2027-01-01",
                end_date="2027-02-01",
                timings="9:00 AM - 12:00 PM",
                mode="offline",
            ),
        )
        assert batches.update_batch(db, batch.id, BatchUpdate(mode="online")).mode == "online"
        batches.delete_batch(db, batch.id)

        announcement = announcements.create(db, AnnouncementIn(message="Local test notice"))
        announcements.delete(db, announcement.id)
        video = videos.create(
            db,
            VideoIn(title="Local video", url="https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        )
        videos.delete(db, video.id)

        storage = LocalStorage(str(storage_dir), "http://testserver")
        banner = banners.create_banner(
            db,
            storage,
            title="Local banner",
            course_code="IBFAP",
            display_order=2,
            is_active=True,
            image_data=_png_bytes(),
        )
        assert len(list((storage_dir / "public" / "banners").glob("*.webp"))) == 2
        banners.delete_banner(db, storage, banner.id)
        assert not list((storage_dir / "public" / "banners").glob("*.webp"))

        first = exam.upload_set(db, 1, "First local set", "first.xlsx", _question_set_bytes("first"), principal.email)
        assert first.exam_set.question_count == 200
        with pytest.raises(ValidationFailed):
            exam.replace_set(db, 1, "Broken replacement", "broken.xlsx", b"not an Excel workbook", principal.email)
        assert exam.list_slots(db)[0].exam_set.name == "First local set"

        replacement = exam.replace_set(
            db,
            1,
            "Replacement local set",
            "replacement.xlsx",
            _question_set_bytes("replacement"),
            principal.email,
        )
        assert replacement.exam_set.name == "Replacement local set"
        exam.delete_set(db, 1)
        assert exam.list_slots(db)[0].exam_set is None

    with Session(engine) as db:
        assert courses.get_course(db, "IBFAP").total_fee_inr == 181000
    _reset_runtime_caches()
