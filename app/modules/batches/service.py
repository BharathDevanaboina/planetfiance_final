from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.error import NotFound, ValidationFailed
from app.core.timeutil import ist_today
from app.modules.batches.models import Batch
from app.modules.batches.schemas import BatchCreate, BatchOut, BatchUpdate
from app.modules.courses import service as courses


def to_out(batch: Batch) -> BatchOut:
    return BatchOut(
        id=batch.id,
        course_code=batch.course.code,
        course_name=batch.course.name,
        start_date=batch.start_date,
        end_date=batch.end_date,
        timings=batch.timings,
        mode=batch.mode,
        is_active=batch.is_active,
    )


def list_batches(db: Session, course_code: str | None = None) -> list[Batch]:
    stmt = select(Batch).order_by(Batch.start_date.desc())
    if course_code:
        course = courses.get_course(db, course_code)
        stmt = stmt.where(Batch.course_code == course.code)
    return list(db.scalars(stmt).unique())


def list_public_batches(db: Session) -> list[Batch]:
    """Active batches that have not finished yet, soonest first."""
    stmt = (
        select(Batch)
        .where(Batch.is_active.is_(True), Batch.end_date >= ist_today())
        .order_by(Batch.start_date)
    )
    return list(db.scalars(stmt).unique())


def get(db: Session, batch_id: uuid.UUID) -> Batch:
    batch = db.get(Batch, batch_id)
    if batch is None:
        raise NotFound("Batch not found.")
    return batch


def create_batch(db: Session, data: BatchCreate) -> BatchOut:
    course = courses.get_course(db, data.course_code)
    batch = Batch(
        course_code=course.code,
        start_date=data.start_date,
        end_date=data.end_date,
        timings=data.timings,
        mode=data.mode,
        is_active=data.is_active,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return to_out(batch)


def update_batch(db: Session, batch_id: uuid.UUID, data: BatchUpdate) -> BatchOut:
    batch = get(db, batch_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(batch, key, value)

    if batch.end_date < batch.start_date:
        raise ValidationFailed("end_date must be on or after start_date.")

    db.commit()
    db.refresh(batch)
    return to_out(batch)


def delete_batch(db: Session, batch_id: uuid.UUID) -> None:
    db.delete(get(db, batch_id))
    db.commit()
