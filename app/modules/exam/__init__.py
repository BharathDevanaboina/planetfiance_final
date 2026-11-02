"""Mock exam (TS ICET pattern): 3 question sets, OTP-verified start, shuffled papers, server-side grading."""

from app.core.module import Module
from app.modules.exam.router import admin_router, public_router

module = Module(
    name="exam",
    description="Exam set management (Excel upload) and the student exam flow. No results are stored.",
    public_router=public_router,
    admin_router=admin_router,
    depends_on=("admin_auth", "registration"),
)
