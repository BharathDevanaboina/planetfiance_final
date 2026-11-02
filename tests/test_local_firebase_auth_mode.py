from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.local_development import initialize_local_dashboard
from app.modules.admin_auth.models import AdminUser


def _settings(database_url: str, **changes) -> Settings:
    values = {
        "app_env": "local",
        "local_firebase_auth_test_mode": True,
        "database_url": database_url,
        "auth_mode": "firebase",
        "storage_backend": "local",
        "sheets_backend": "fake",
        "gcp_project_id": "planetfiance-local-test",
        "firebase_web_api_key": "public-web-key",
        "firebase_web_auth_domain": "planetfiance-local-test.firebaseapp.com",
        "firebase_web_app_id": "local-test-app-id",
    }
    values.update(changes)
    return Settings(**values)


def test_local_firebase_auth_mode_uses_separate_sqlite_without_an_admin(tmp_path) -> None:
    settings = _settings(f"sqlite:///{(tmp_path / 'firebase-auth-test.db').as_posix()}")
    settings.validate_for_environment()
    initialize_local_dashboard(settings, include_local_admin=False)

    engine = create_engine(settings.sqlalchemy_url)
    assert "admin_users" in inspect(engine).get_table_names()
    with Session(engine) as db:
        assert db.scalar(select(AdminUser)) is None


def test_local_firebase_auth_mode_rejects_fake_auth(tmp_path) -> None:
    settings = _settings(
        f"sqlite:///{(tmp_path / 'firebase-auth-test.db').as_posix()}",
        auth_mode="fake",
    )
    with pytest.raises(RuntimeError, match='AUTH_MODE="firebase"'):
        settings.validate_for_environment()
