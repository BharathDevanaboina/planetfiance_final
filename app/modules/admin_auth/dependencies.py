"""Reusable require_admin dependency for admin routes."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_identity_verifier
from app.core.error import Forbidden, Unauthorized
from app.core.identity import IdentityVerifier
from app.modules.admin_auth import service


@dataclass(frozen=True)
class AdminPrincipal:
    admin_id: str
    email: str
    firebase_uid: str


def require_admin(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    verifier: IdentityVerifier = Depends(get_identity_verifier),
) -> AdminPrincipal:
    if not authorization or not authorization.startswith("Bearer "):
        raise Unauthorized("Missing admin sign-in.")

    identity = verifier.verify_admin_token(authorization.removeprefix("Bearer ").strip())
    if identity.sign_in_provider != "google.com":
        raise Forbidden("Administrator access requires Google Sign-In.", code="GOOGLE_SIGN_IN_REQUIRED")
    if not identity.email or not identity.email_verified:
        raise Forbidden("Your email address is not verified.", code="EMAIL_NOT_VERIFIED")
    admin = service.get_active_admin(db, identity.uid, identity.email)
    if admin is None:
        raise Forbidden("This account does not have admin access.", code="NOT_AN_ADMIN")

    service.record_login(db, admin)
    return AdminPrincipal(
        admin_id=str(admin.id),
        email=admin.email,
        firebase_uid=identity.uid,
    )
