# Reconstructed from the supplied screenshots.
# IMPORTANT: This is a partial transcription. The screenshots do not show the
# complete service.py file, and some lines at the top/bottom are outside the
# captured area. Verify against the original source before using in production.

from __future__ import annotations

import random
import secrets
import time
import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.error import Conflict, Gone, NotFound, ServiceUnavailable, ValidationFailed
from app.core.identity import IdentityVerifier
from app.core.sheets import SheetsClient, SheetsError
from app.core.tokens import sign_token, verify_token
from app.modules.exam import paper
from app.modules.exam.constants import REQUIRED_SECTION_COUNTS, SLOTS, TOTAL_QUESTIONS
from app.modules.exam.importer import ImportReport, parse_workbook
from app.modules.exam.models import ExamOption, ExamPassage, ExamQuestion, ExamSet
from app.modules.exam.schemas import (
    ExamInfo,
    ExamPreview,
    ExamResult,
    ExamSetOut,
    ExamStartResponse,
    ExamSubmitRequest,
    IssueOut,
    QuestionPreview,
    SlotOut,
    UploadResult,
    ValidationReport,
)
from app.modules.registration import service as registration
from app.modules.registration.schemas import RegistrationSubmission

ATTEMPT_AUDIENCE = "exam-attempt"
SHEET_HEADERS = registration.SHEET_BASE_HEADERS + ["Exam Set"]


# ----- admin -----


def _issues(items) -> list[IssueOut]:
    return [IssueOut(sheet=i.sheet, row=i.row, message=i.message) for i in items]


def to_report(report: ImportReport) -> ValidationReport:
    return ValidationReport(
        ok=report.ok,
        question_count=len(report.questions),
        section_counts=report.section_counts,
        subsection_counts=report.subsection_counts,
        passage_count=len(report.passages),
        errors=_issues(report.errors),
        warnings=_issues(report.warnings),
    )


def _set_out(s: ExamSet) -> ExamSetOut:
    return ExamSetOut.model_validate(s, from_attributes=True)


def list_slots(db: Session) -> list[SlotOut]:
    by_slot = {s.slot: s for s in db.scalars(select(ExamSet))}
    return [
        SlotOut(slot=slot, exam_set=_set_out(by_slot[slot]) if slot in by_slot else None) for slot in SLOTS
    ]


def validate_file(data: bytes) -> ValidationReport:
    return to_report(parse_workbook(data))


def preview_file(data: bytes, *, limit: int = 12) -> ExamPreview:
    """Validate a file and return a bounded, admin-only question preview."""
    report = parse_workbook(data)
    return ExamPreview(
        report=to_report(report),
        questions=[
            QuestionPreview(
                section=question.section,
                subsection=question.subsection,
                content=question.content,
                options=[text for _label, text in question.options],
            )
            for question in report.questions[:limit]
        ],
    )


def upload_set(
    db: Session, slot: int, name: str | None, filename: str, data: bytes, uploaded_by: str
) -> UploadResult:
    if slot not in SLOTS:
        raise NotFound("Slot must be 1, 2 or 3.", code="INVALID_SLOT")
    if db.scalar(select(ExamSet).where(ExamSet.slot == slot)):
        raise Conflict(
            f"Slot {slot} already has a set. Delete it first, then upload the new one.",
            code="SLOT_OCCUPIED",
        )

    report = parse_workbook(data)
    if not report.ok:
        raise ValidationFailed(
            "The file has problems. Fix them and upload again.",
            code="INVALID_QUESTION_SET",
            extra={"report": to_report(report).model_dump()},
        )

    exam_set = ExamSet(
        slot=slot,
        name=(name or "").strip()[:100] or f"Set {slot}",
        source_filename=filename[:255],
        question_count=len(report.questions),
        uploaded_by=uploaded_by,
    )
    db.add(exam_set)
    db.flush()

    passage_ids: dict[str, uuid.UUID] = {}
    for key, p in report.passages.items():
        if not p.section:
            continue  # unused passage (reported as a warning)
        row = ExamPassage(
            exam_set_slot=exam_set.slot,
            passage_key=key,
            section=p.section,
            content=p.content,
        )
        db.add(row)
        db.flush()
        passage_ids[key] = row.id

    for position, q in enumerate(report.questions, start=1):
        question = ExamQuestion(
            exam_set_slot=exam_set.slot,
            passage_id=passage_ids.get(q.passage_key) if q.passage_key else None,
            position=position,
            section=q.section,
            subsection=q.subsection,
            content=q.content,
        )
        db.add(question)
        db.flush()
        db.add_all(
            [
                ExamOption(
                    question_id=question.id,
                    label=label,
                    content=text,
                    is_correct=(label == q.correct),
                )
                for label, text in q.options
            ]
        )

    db.commit()
    db.refresh(exam_set)
    return UploadResult(
        exam_set=_set_out(exam_set),
        warnings=_issues(report.warnings),
    )


def delete_set(db: Session, slot: int) -> None:
    exam_set = db.scalar(select(ExamSet).where(ExamSet.slot == slot))
    if exam_set is None:
        raise NotFound(f"Slot {slot} is already empty.", code="SLOT_EMPTY")

    question_ids = select(ExamQuestion.id).where(ExamQuestion.exam_set_slot == exam_set.slot)
    db.execute(delete(ExamOption).where(ExamOption.question_id.in_(question_ids)))
    db.execute(delete(ExamQuestion).where(ExamQuestion.exam_set_slot == exam_set.slot))
    db.execute(delete(ExamPassage).where(ExamPassage.exam_set_slot == exam_set.slot))
    db.execute(delete(ExamSet).where(ExamSet.slot == exam_set.slot))
    db.commit()
    # The screenshot shows `paper.evict(exam_set.id)` after the commit.
    paper.evict(exam_set.slot)


# ----- student ---------------------------------------------------------------


def exam_info(db: Session, settings: Settings) -> ExamInfo:
    count = db.scalar(select(func.count()).select_from(ExamSet)) or 0
    return ExamInfo(
        available=count > 0,
        duration_minutes=settings.exam_duration_minutes,
        total_questions=TOTAL_QUESTIONS,
        sections=dict(REQUIRED_SECTION_COUNTS),
    )


def start_exam(
    db: Session,
    sheets: SheetsClient,
    verifier: IdentityVerifier,
    settings: Settings,
    submission: RegistrationSubmission,
) -> ExamStartResponse:
    verified = registration.verify_submission(submission, verifier, settings)
    set_slots = list(db.scalars(select(ExamSet.slot)))
    if not set_slots:
        raise ServiceUnavailable(
            "The mock exam is not available right now. Please try again later.",
            code="NO_EXAM_SETS",
        )

    rng = random.SystemRandom()
    snapshot = paper.load_snapshot(db, rng.choice(set_slots))
    if snapshot is None:  # deleted in the meantime
        raise ServiceUnavailable("Please try again.", code="NO_EXAM_SETS")

    try:
        sheets.append_row(
            settings.sheets_tab_exam,
            SHEET_HEADERS,
            verified.sheet_values() + [snapshot.name],
        )
    except SheetsError as exc:
        raise ServiceUnavailable(
            "Exam registration could not be recorded. Please try again later.",
            code="LEAD_DELIVERY_UNAVAILABLE",
        ) from exc
    registration.release_phone_user(verified, verifier, settings)

    duration = settings.exam_duration_minutes * 60
    started = int(time.time())
    token = sign_token(
        {"sid": str(snapshot.slot), "st": started, "dur": duration, "n": secrets.token_hex(4)},
        audience=ATTEMPT_AUDIENCE,
        expires_in_seconds=duration + settings.exam_submit_grace_seconds,
        secret=settings.token_secret,
    )
    sections = paper.build_paper(snapshot, random.Random(rng.getrandbits(64)))
    return ExamStartResponse(
        attempt_token=token,
        set_name=snapshot.name,
        duration_seconds=duration,
        started_at=datetime.fromtimestamp(started, UTC),
        ends_at=datetime.fromtimestamp(started + duration, UTC),
        total_questions=sum(s["question_count"] for s in sections),
        sections=sections,
    )


def submit_exam(db: Session, settings: Settings, body: ExamSubmitRequest) -> ExamResult:
    claims = verify_token(
        body.attempt_token,
        audience=ATTEMPT_AUDIENCE,
        secret=settings.token_secret,
    )
    snapshot = paper.load_snapshot(db, int(claims["sid"]))
    if snapshot is None:
        raise Gone(
            "This question set has been replaced. Please start a new exam.",
            code="SET_REPLACED",
        )

    answers: dict[uuid.UUID, uuid.UUID | None] = {}
    for answer in body.answers:
        question = snapshot.questions.get(answer.question_id)
        if question is None:
            raise ValidationFailed(
                "An answer refers to a question that is not in this exam.",
                code="UNKNOWN_QUESTION",
            )
        if answer.question_id in answers:
            raise ValidationFailed("A question was answered twice.", code="DUPLICATE_ANSWER")
        if answer.option_id is not None and answer.option_id not in {
            option.id for option in question.options
        }:
            raise ValidationFailed(
                "An answer refers to an option that does not belong to its question.",
                code="UNKNOWN_OPTION",
            )
        answers[answer.question_id] = answer.option_id

    result = paper.grade(snapshot, answers)
    late = time.time() > claims["st"] + claims["dur"]
    return ExamResult(
        set_name=snapshot.name,
        submitted_after_time_limit=late,
        **result,
    )
