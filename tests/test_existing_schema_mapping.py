import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, configure_mappers

import app.models  # noqa: F401
from app import cli
from app.core.error import Forbidden, Unauthorized
from app.core.identity import AdminIdentity, FakeIdentityVerifier
from app.core.models import Base
from app.modules.admin_auth import service as admin_service
from app.modules.admin_auth.dependencies import require_admin


def test_models_target_verified_existing_table_names() -> None:
    configure_mappers()
    expected = {
        "course",
        "batch",
        "banner",
        "announcement",
        "site_setting",
        "video",
        "exam_set",
        "exam_passage",
        "exam_question",
        "exam_option",
    }
    assert expected.issubset(Base.metadata.tables)


def test_admin_authorization_requires_matching_firebase_uid_and_email() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin = admin_service.initialize_admin(
            db,
            firebase_uid="verified-firebase-uid",
            email="admin@example.com",
            full_name="Admin",
        )
        assert admin_service.get_active_admin(db, "verified-firebase-uid", "admin@example.com").id == admin.id
        assert admin_service.get_active_admin(db, "wrong-uid", "admin@example.com") is None
        assert admin_service.get_active_admin(db, "verified-firebase-uid", "other@example.com") is None


def test_second_admin_registration_is_refused_by_service_and_database() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        admin_service.initialize_admin(db, "first-uid", "first@example.com", "First")

        with pytest.raises(ValueError, match="sole administrator"):
            admin_service.initialize_admin(db, "second-uid", "second@example.com", "Second")

        from app.modules.admin_auth.models import AdminUser

        db.add(AdminUser(firebase_uid="bypass-uid", email="bypass@example.com"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()


def test_admin_authorization_rejects_non_email_password_firebase_tokens() -> None:
    class GoogleVerifier:
        def verify_admin_token(self, _: str) -> AdminIdentity:
            return AdminIdentity(
                uid="verified-firebase-uid",
                email="admin@example.com",
                email_verified=True,
                sign_in_provider="google.com",
                mfa_verified=False,
            )

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, pytest.raises(Forbidden, match="Email/Password"):
        require_admin("Bearer test-token", db, GoogleVerifier())


def test_only_the_registered_email_password_identity_is_authorized() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    verifier = FakeIdentityVerifier()
    with Session(engine) as db:
        admin_service.initialize_admin(db, "uid-admin@example.com", "admin@example.com", "Admin")
        principal = require_admin("Bearer fake-admin:admin@example.com", db, verifier)
        assert principal.firebase_uid == "uid-admin@example.com"

        with pytest.raises(Forbidden, match="does not have admin access"):
            require_admin("Bearer fake-admin:other@example.com", db, verifier)


def test_admin_api_rejects_requests_without_a_bearer_token() -> None:
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db, pytest.raises(Unauthorized, match="Missing admin sign-in"):
        require_admin(None, db, FakeIdentityVerifier())


def test_cli_exposes_only_the_one_time_admin_registration_command(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as result:
        cli.main(["--help"])

    assert result.value.code == 0
    help_text = capsys.readouterr().out
    assert "grant-existing-admin" in help_text
    assert "create-admin" not in help_text
    assert "deactivate-admin" not in help_text
    assert "flush-lead-sync" not in help_text
