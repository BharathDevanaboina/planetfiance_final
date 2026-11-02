from __future__ import annotations

import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error import NotFound
from app.core.media import delete_files
from app.core.storage import FileStorage
from app.core.uploads import validate_pdf
from app.modules.brochures.models import Brochure
from app.modules.brochures.schemas import BrochureStatus
from app.modules.courses import service as courses


def _find(db: Session, course_code: str) -> Brochure | None:
    return db.scalar(select(Brochure).where(Brochure.course_code == course_code))


def course_codes_with_brochure(db: Session) -> set[str]:
    """Return brochure-linked course codes when the optional metadata table exists."""
    return set(db.scalars(select(Brochure.course_code)))


def list_status(db: Session) -> list[BrochureStatus]:
    by_course = {b.course_code: b for b in db.scalars(select(Brochure)).unique()}
    result: list[BrochureStatus] = []

    for course in courses.list_courses(db):
        brochure = by_course.get(course.code)
        result.append(
            BrochureStatus(
                course_code=course.code,
                course_name=course.name,
                has_brochure=brochure is not None,
                original_filename=brochure.original_filename if brochure else None,
                size_bytes=brochure.size_bytes if brochure else None,
                updated_at=brochure.updated_at if brochure else None,
            )
        )
    return result


def upload_brochure(
    db: Session,
    storage: FileStorage,
    code: str,
    data: bytes,
    filename: str,
) -> BrochureStatus:
    course = courses.get_course(db, code)
    validate_pdf(data)

    path = f"private/brochures/{course.code}/{uuid.uuid4().hex}.pdf"
    storage.save_private(path, data, "application/pdf")

    existing = _find(db, course.code)
    old_path = existing.file_path if existing else None

    if existing:
        existing.file_path = path
        existing.original_filename = filename[:255]
        existing.size_bytes = len(data)
    else:
        db.add(
            Brochure(
                course_code=course.code,
                file_path=path,
                original_filename=filename[:255],
                size_bytes=len(data),
            )
        )

    try:
        db.commit()
    except Exception:
        db.rollback()
        delete_files(storage, path)
        raise

    # Delete the old private file only after the database commit succeeds.
    delete_files(storage, old_path)

    return next(item for item in list_status(db) if item.course_code == course.code)


def delete_brochure(db: Session, storage: FileStorage, code: str) -> None:
    course = courses.get_course(db, code)
    existing = _find(db, course.code)
    if existing is None:
        raise NotFound("This course has no brochure.", code="BROCHURE_NOT_FOUND")

    path = existing.file_path
    db.delete(existing)
    db.commit()
    delete_files(storage, path)


def download_name(course_name: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9]+", "-", course_name).strip("-") or "course"
    return f"{safe}-Brochure.pdf"


def read_brochure(
    db: Session,
    storage: FileStorage,
    code: str,
) -> tuple[bytes, str, str]:
    """Return (PDF bytes, download filename, course name)."""
    course = courses.get_course(db, code)
    existing = _find(db, course.code)
    if existing is None:
        raise NotFound(
            "The brochure for this course is not available yet.",
            code="BROCHURE_NOT_FOUND",
        )
    return (
        storage.read(existing.file_path),
        download_name(course.name),
        course.name,
    )
