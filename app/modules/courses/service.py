from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error import NotFound, ValidationFailed
from app.core.formatting import format_inr
from app.modules.courses.models import Course
from app.modules.courses.schemas import CourseOut, CourseUpdate, FeeBreakupOut


def _fee_items(value: object) -> list[dict]:
    """Return valid fee rows without rewriting a legacy text value on read."""
    return value if isinstance(value, list) else []


def list_courses(db: Session, *, active_only: bool = False) -> list[Course]:
    stmt = select(Course).order_by(Course.display_order, Course.name)
    if active_only:
        stmt = stmt.where(Course.is_active.is_(True))
    return list(db.scalars(stmt))


def get_course(db: Session, code: str) -> Course:
    course = db.scalar(select(Course).where(Course.code == code.upper()))
    if course is None:
        raise NotFound(f"Course '{code}' does not exist.", code="COURSE_NOT_FOUND")
    return course


def to_out(course: Course) -> CourseOut:
    return CourseOut(
        code=course.code,
        name=course.name,
        duration_text=course.duration_text,
        summary=course.summary,
        eligibility=course.eligibility,
        total_fee_inr=course.total_fee_inr,
        total_fee_display=format_inr(course.total_fee_inr),
        fee_note=course.fee_note,
        fee_breakup=[
            FeeBreakupOut(
                label=item["label"],
                amount_inr=item["amount_inr"],
                amount_display=format_inr(item["amount_inr"]),
            )
            for item in _fee_items(course.fee_breakup)
        ],
        display_order=course.display_order,
        is_active=course.is_active,
        updated_at=course.updated_at,
    )


def update_course(db: Session, code: str, data: CourseUpdate) -> CourseOut:
    course = get_course(db, code)
    changes = data.model_dump(exclude_unset=True)

    if changes.get("name") is None:
        changes.pop("name", None)
    if changes.get("duration_text") is None:
        changes.pop("duration_text", None)
    if "fee_breakup" in changes and changes["fee_breakup"] is None:
        changes["fee_breakup"] = []

    total = changes.get("total_fee_inr", course.total_fee_inr)
    breakup = changes.get("fee_breakup", _fee_items(course.fee_breakup))
    breakup_total = sum(
        item.amount_inr if hasattr(item, "amount_inr") else item["amount_inr"] for item in breakup
    )
    if breakup and breakup_total != total:
        raise ValidationFailed(
            "The fee breakup must add up to the total fee. Update both, or send an empty breakup.",
            code="FEE_BREAKUP_MISMATCH",
        )

    if "fee_breakup" in changes:
        changes["fee_breakup"] = [
            item.model_dump() if hasattr(item, "model_dump") else item for item in changes["fee_breakup"]
        ]

    for key, value in changes.items():
        setattr(course, key, value)

    db.commit()
    db.refresh(course)
    return to_out(course)
