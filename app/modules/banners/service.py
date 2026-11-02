from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error import NotFound
from app.core.media import delete_files, store_image
from app.core.storage import FileStorage
from app.core.validation import clean_text
from app.modules.banners.models import Banner
from app.modules.banners.schemas import BannerOut, BannerUpdate
from app.modules.courses import service as courses


def to_out(banner: Banner) -> BannerOut:
    return BannerOut(
        id=banner.id,
        title=banner.title,
        course_code=banner.course.code if banner.course else None,
        image_url=banner.image_url,
        thumb_url=banner.thumb_url,
        image_width=banner.image_width,
        image_height=banner.image_height,
        display_order=banner.display_order,
        is_active=banner.is_active,
    )


def list_banners(db: Session, *, active_only: bool = False) -> list[Banner]:
    stmt = select(Banner).order_by(Banner.display_order, Banner.created_at)
    if active_only:
        stmt = stmt.where(Banner.is_active.is_(True))
    return list(db.scalars(stmt).unique())


def _get(db: Session, banner_id: uuid.UUID) -> Banner:
    banner = db.get(Banner, banner_id)
    if banner is None:
        raise NotFound("Banner not found.")
    return banner


def _course_code(db: Session, course_code: str | None) -> str | None:
    if not course_code:
        return None
    return courses.get_course(db, course_code).code


def create_banner(
    db: Session,
    storage: FileStorage,
    *,
    title: str,
    course_code: str | None,
    display_order: int,
    is_active: bool,
    image_data: bytes,
) -> BannerOut:
    title = clean_text(title, max_length=150, allow_empty=False)
    resolved_course_code = _course_code(db, course_code)
    stored = store_image(storage, "banners", image_data)
    banner = Banner(
        title=title,
        course_code=resolved_course_code,
        image_path=stored.large_path,
        image_url=stored.large_url,
        thumb_path=stored.thumb_path,
        thumb_url=stored.thumb_url,
        image_width=stored.width,
        image_height=stored.height,
        display_order=display_order,
        is_active=is_active,
    )
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return to_out(banner)


def update_banner(db: Session, banner_id: uuid.UUID, data: BannerUpdate) -> BannerOut:
    banner = _get(db, banner_id)
    fields = data.model_fields_set

    if "title" in fields and data.title is not None:
        banner.title = clean_text(data.title, max_length=150, allow_empty=False)
    if "course_code" in fields:
        banner.course_code = _course_code(db, data.course_code)
    if "display_order" in fields and data.display_order is not None:
        banner.display_order = data.display_order
    if "is_active" in fields and data.is_active is not None:
        banner.is_active = data.is_active

    db.commit()
    db.refresh(banner)
    return to_out(banner)


def replace_image(
    db: Session,
    storage: FileStorage,
    banner_id: uuid.UUID,
    image_data: bytes,
) -> BannerOut:
    banner = _get(db, banner_id)
    old_files = (banner.image_path, banner.thumb_path)
    stored = store_image(storage, "banners", image_data)

    banner.image_path = stored.large_path
    banner.image_url = stored.large_url
    banner.thumb_path = stored.thumb_path
    banner.thumb_url = stored.thumb_url
    banner.image_width = stored.width
    banner.image_height = stored.height

    db.commit()
    db.refresh(banner)
    delete_files(storage, *old_files)
    return to_out(banner)


def delete_banner(db: Session, storage: FileStorage, banner_id: uuid.UUID) -> None:
    banner = _get(db, banner_id)
    paths = (banner.image_path, banner.thumb_path)
    db.delete(banner)
    db.commit()
    delete_files(storage, *paths)
