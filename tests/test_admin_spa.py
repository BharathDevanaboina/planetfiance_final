from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.modules import ALL_MODULES, select_modules


def test_module_registry_selects_existing_modules_and_validates_dependencies() -> None:
    assert select_modules("all") == ALL_MODULES
    assert [module.name for module in select_modules("admin_auth,registration,exam")] == [
        "admin_auth",
        "registration",
        "exam",
    ]


def test_admin_spa_and_public_firebase_config_are_served(tmp_path: Path) -> None:
    """The browser assets and Firebase client config stay available together."""
    app = create_app(
        Settings(
            app_env="test",
            database_url="sqlite://",
            auth_mode="fake",
            storage_backend="local",
            local_storage_dir=str(tmp_path / "storage"),
            sheets_backend="fake",
            app_check_enabled=False,
            firebase_web_api_key="public-test-key",
            firebase_web_auth_domain="example.firebaseapp.com",
            firebase_web_app_id="test-app-id",
        )
    )
    client = TestClient(app)

    page = client.get("/admin/")
    assert page.status_code == 200
    assert "<title>College Admin</title>" in page.text
    assert 'src="/admin/app.js"' in page.text

    app_script = client.get("/admin/app.js")
    assert app_script.status_code == 200
    assert "signInWithEmailAndPassword" in app_script.text
    assert "signInWithPopup" not in app_script.text
    assert "GoogleAuthProvider" not in app_script.text
    assert "TotpMultiFactorGenerator" not in app_script.text
    assert "auth/configuration-not-found" in app_script.text

    config = client.get("/admin/firebase-config.js")
    assert config.status_code == 200
    assert "public-test-key" in config.text
    assert config.headers["cache-control"] == "no-store"
