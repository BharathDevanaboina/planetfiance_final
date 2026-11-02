from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.admin_auth import service
from app.modules.admin_auth.dependencies import AdminPrincipal, require_admin
from app.modules.admin_auth.schemas import AdminProfile

admin_router = APIRouter(tags=["Admin: account"], dependencies=[Depends(require_admin)])


@admin_router.get("/me", response_model=AdminProfile, summary="Who am I (checks admin access)")
def me(principal: AdminPrincipal = Depends(require_admin), db: Session = Depends(get_db)) -> AdminProfile:
    admin = service.get_active_admin(db, principal.firebase_uid, principal.email)
    return AdminProfile(
        email=principal.email,
        full_name=admin.full_name if admin else None,
        firebase_uid=principal.firebase_uid,
        last_login_at=admin.last_login_at if admin else None,
    )
