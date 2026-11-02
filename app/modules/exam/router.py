from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Path, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.dependencies import get_identity_verifier, get_sheets, require_app_check
from app.core.identity import IdentityVerifier
from app.core.rate_limit import rate_limit
from app.core.sheets import SheetsClient
from app.core.uploads import read_upload
from app.modules.admin_auth.dependencies import AdminPrincipal, require_admin
from app.modules.exam import service
from app.modules.exam.schemas import (
    ExamInfo,
    ExamPreview,
    ExamResult,
    ExamStartResponse,
    ExamSubmitRequest,
    SlotOut,
    UploadResult,
    ValidationReport,
)
from app.modules.exam.template import build_template
from app.modules.registration.schemas import RegistrationSubmission

public_router = APIRouter(prefix="/exam", tags=["Public: mock exam"])
admin_router = APIRouter(
    prefix="/exam",
    tags=["Admin: exam sets"],
    dependencies=[Depends(require_admin)],
)

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ---- student ----------------------------------------------------------------


@public_router.get(
    "/info",
    response_model=ExamInfo,
    summary="Is the exam available, duration and pattern",
)
def exam_info(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ExamInfo:
    return service.exam_info(db, settings)


@public_router.post(
    "/start",
    response_model=ExamStartResponse,
    summary="Submit the registration form (after OTP) and receive a shuffled paper",
    dependencies=[
        Depends(require_app_check),
        Depends(rate_limit("exam_start", limit=10, window_seconds=3600)),
    ],
)
def start_exam(
    body: RegistrationSubmission,
    db: Session = Depends(get_db),
    sheets: SheetsClient = Depends(get_sheets),
    verifier: IdentityVerifier = Depends(get_identity_verifier),
    settings: Settings = Depends(get_settings),
) -> ExamStartResponse:
    return service.start_exam(db, sheets, verifier, settings, body)


@public_router.post(
    "/submit",
    response_model=ExamResult,
    summary="Submit answers and get the score and review (nothing is stored)",
    dependencies=[Depends(rate_limit("exam_submit", limit=30, window_seconds=3600))],
)
def submit_exam(
    body: ExamSubmitRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ExamResult:
    return service.submit_exam(db, settings, body)


# ---- admin ------------------------------------------------------------------


@admin_router.post(
    "/sets/preview",
    response_model=ExamPreview,
    summary="Validate an Excel file and preview questions without saving it",
)
def preview_set(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> ExamPreview:
    return service.preview_file(read_upload(file, max_mb=settings.max_excel_upload_mb))


@admin_router.get(
    "/sets",
    response_model=list[SlotOut],
    summary="The three set slots and what is in them",
)
def list_sets(db: Session = Depends(get_db)) -> list[SlotOut]:
    return service.list_slots(db)


@admin_router.get("/template", summary="Download the Excel template")
def download_template() -> Response:
    return Response(
        build_template(),
        media_type=XLSX,
        headers={"Content-Disposition": 'attachment; filename="exam-question-set-template.xlsx"'},
    )


@admin_router.post(
    "/sets/validate",
    response_model=ValidationReport,
    summary="Check an Excel file without saving it",
)
def validate_set(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> ValidationReport:
    return service.validate_file(read_upload(file, max_mb=settings.max_excel_upload_mb))


@admin_router.post(
    "/sets/{slot}",
    response_model=UploadResult,
    status_code=201,
    summary="Upload a set into an empty slot",
)
def upload_set(
    slot: int = Path(ge=1, le=3),
    file: UploadFile = File(...),
    name: str | None = Form(default=None, description='Display name, e.g. "Set 1"'),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    admin: AdminPrincipal = Depends(require_admin),
) -> UploadResult:
    data = read_upload(file, max_mb=settings.max_excel_upload_mb)
    return service.upload_set(db, slot, name, file.filename or "questions.xlsx", data, admin.email)


@admin_router.put(
    "/sets/{slot}",
    response_model=UploadResult,
    summary="Atomically replace a populated question set",
)
def replace_set(
    slot: int = Path(ge=1, le=3),
    file: UploadFile = File(...),
    name: str | None = Form(default=None, description='Display name, e.g. "Set 1"'),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    admin: AdminPrincipal = Depends(require_admin),
) -> UploadResult:
    data = read_upload(file, max_mb=settings.max_excel_upload_mb)
    return service.replace_set(db, slot, name, file.filename or "questions.xlsx", data, admin.email)


@admin_router.delete(
    "/sets/{slot}",
    status_code=204,
    summary="Delete the set in a slot",
)
def delete_set(
    slot: int = Path(ge=1, le=3),
    db: Session = Depends(get_db),
) -> Response:
    service.delete_set(db, slot)
    return Response(status_code=204)
