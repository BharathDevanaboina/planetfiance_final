"""Checks Firebase tokens: admin sign-in, student phone OTP and App Check.

Two implementations share one interface:

- ``FirebaseIdentityVerifier`` — real Firebase (staging and production).
- ``FakeIdentityVerifier`` — for local development and tests, no Firebase needed.

Fake tokens look like ``fake-admin:admin@college.com:mfa`` or
``fake-phone:+919876543210``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

from app.core.error import Unauthorized

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AdminIdentity:
    uid: str
    email: str
    email_verified: bool
    sign_in_provider: str
    mfa_verified: bool


@dataclass(frozen=True)
class PhoneIdentity:
    uid: str
    phone_number: str  # E.164, e.g. +919876543210
    sign_in_provider: str
    auth_time: int  # Unix seconds when the OTP was completed


class IdentityVerifier(Protocol):
    def verify_admin_token(self, token: str) -> AdminIdentity: ...

    def verify_phone_token(self, token: str) -> PhoneIdentity: ...

    def verify_app_check(self, token: str) -> None: ...

    def delete_user(self, uid: str) -> None: ...


class FirebaseIdentityVerifier:
    def __init__(
        self,
        project_id: str | None,
        storage_bucket: str | None,
    ) -> None:
        import firebase_admin

        try:
            self._app = firebase_admin.get_app()
        except ValueError:
            options = {
                key: value
                for key, value in (
                    ("projectId", project_id),
                    ("storageBucket", storage_bucket),
                )
                if value
            }
            self._app = firebase_admin.initialize_app(options=options)

    def _decode(self, token: str, check_revoked: bool) -> dict:
        from firebase_admin import auth

        try:
            return auth.verify_id_token(
                token,
                app=self._app,
                check_revoked=check_revoked,
            )
        except (
            auth.RevokedIdTokenError,
            auth.UserDisabledError,
            auth.UserNotFoundError,
        ) as exc:
            raise Unauthorized(
                "Your session has been revoked. Please sign in again.",
                code="TOKEN_REVOKED",
            ) from exc
        except auth.ExpiredIdTokenError as exc:
            raise Unauthorized(
                "Your session has expired. Please sign in again.",
                code="TOKEN_EXPIRED",
            ) from exc
        except (
            auth.InvalidIdTokenError,
            auth.CertificateFetchError,
            ValueError,
        ) as exc:
            raise Unauthorized(
                "Invalid sign-in token.",
                code="TOKEN_INVALID",
            ) from exc

    def verify_admin_token(self, token: str) -> AdminIdentity:
        claims = self._decode(token, check_revoked=True)
        firebase_claims = claims.get("firebase", {}) or {}
        return AdminIdentity(
            uid=claims["uid"],
            email=(claims.get("email") or "").lower(),
            email_verified=bool(claims.get("email_verified")),
            sign_in_provider=str(firebase_claims.get("sign_in_provider") or ""),
            mfa_verified=bool(firebase_claims.get("sign_in_second_factor")),
        )

    def verify_phone_token(self, token: str) -> PhoneIdentity:
        # Phone users are deleted after a successful lead submission. Checking
        # revocation makes that deletion effective immediately and prevents a
        # still-unexpired ID token from being replayed for more submissions.
        claims = self._decode(token, check_revoked=True)
        firebase_claims = claims.get("firebase", {}) or {}
        return PhoneIdentity(
            uid=claims["uid"],
            phone_number=claims.get("phone_number") or "",
            sign_in_provider=(firebase_claims.get("sign_in_provider") or ""),
            auth_time=int(claims.get("auth_time") or 0),
        )

    def verify_app_check(self, token: str) -> None:
        from firebase_admin import app_check

        try:
            app_check.verify_token(token, app=self._app)
        except Exception as exc:
            raise Unauthorized(
                "App verification failed. Please reload the page.",
                code="APP_CHECK_FAILED",
            ) from exc

    def delete_user(self, uid: str) -> None:
        from firebase_admin import auth

        try:
            auth.delete_user(uid, app=self._app)
        except Exception:
            logger.warning(
                "Could not delete Firebase phone user",
                extra={"uid": uid},
                exc_info=True,
            )


class FakeIdentityVerifier:
    """Accepts predictable tokens. Never allowed in staging or production."""

    def __init__(self) -> None:
        self.deleted_users: list[str] = []

    def verify_admin_token(self, token: str) -> AdminIdentity:
        parts = token.split(":")
        if len(parts) < 2 or parts[0] != "fake-admin":
            raise Unauthorized(
                "Invalid sign-in token.",
                code="TOKEN_INVALID",
            )
        email = parts[1].lower()
        return AdminIdentity(
            uid=f"uid-{email}",
            email=email,
            email_verified=True,
            sign_in_provider="google.com",
            mfa_verified="mfa" in parts[2:],
        )

    def verify_phone_token(self, token: str) -> PhoneIdentity:
        parts = token.split(":")
        if len(parts) < 2 or parts[0] != "fake-phone":
            raise Unauthorized(
                "Invalid verification token.",
                code="TOKEN_INVALID",
            )
        auth_time = int(parts[2]) if len(parts) > 2 else int(time.time())
        return PhoneIdentity(
            uid=f"uid-{parts[1]}",
            phone_number=parts[1],
            sign_in_provider="phone",
            auth_time=auth_time,
        )

    def verify_app_check(self, token: str) -> None:
        if token != "fake-app-check":  # noqa: S105 - fake verifier for local use only
            raise Unauthorized(
                "App verification failed. Please reload the page.",
                code="APP_CHECK_FAILED",
            )

    def delete_user(self, uid: str) -> None:
        self.deleted_users.append(uid)
