"""Application settings.

Every setting is read from an environment variable with the same name in upper case
(for example, `storage_bucket` -> `$STORAGE_BUCKET`). Locally, the values can also come
from a `.env` file. See docs/03-configuration.md for the full list.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url

Environment = Literal["local", "test", "staging", "production"]
DEV_TOKEN_SECRET = "local-development-only-secret-change-me-0123456789"  # noqa: S105


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- General ---------------------------------------------------------------
    app_env: Environment = "local"
    app_name: str = "college-backend"
    log_level: str = "INFO"
    local_dashboard_mode: bool = False
    local_firebase_auth_test_mode: bool = False
    enabled_modules: str = Field(
        default="all",
        description="Comma-separated module names to run in this service, or 'all'.",
    )
    cors_allowed_origins: str = Field(default="", description="Comma-separated list of allowed origins.")

    # --- Database --------------------------------------------------------------
    database_url: str | None = Field(default=None, description="Full SQLAlchemy URL. Overrides DB_* parts.")
    db_user: str = "college"
    db_password: str = ""
    db_name: str = "college"
    db_host: str = "localhost"
    db_port: int = 5432
    cloud_sql_connection_name: str | None = Field(
        default=None,
        description="PROJECT:REGION:INSTANCE. When set, connects through the Cloud SQL socket.",
    )
    db_pool_size: int = 5
    db_max_overflow: int = 5

    # --- Firebase / Google Cloud -----------------------------------------------
    gcp_project_id: str | None = None
    # Firebase web-app configuration is public by design (unlike a service
    # account). The admin SPA reads it from a same-origin config endpoint.
    firebase_web_api_key: str | None = None
    firebase_web_auth_domain: str | None = None
    firebase_web_app_id: str | None = None
    firebase_web_messaging_sender_id: str | None = None
    firebase_web_measurement_id: str | None = None
    auth_mode: Literal["firebase", "fake"] = "firebase"
    app_check_enabled: bool = True
    otp_max_age_seconds: int = 600
    delete_firebase_phone_user: bool = True

    # --- File storage ----------------------------------------------------------
    storage_backend: Literal["firebase", "local"] = "firebase"
    storage_bucket: str | None = None
    local_storage_dir: str = "/var/storage"
    public_base_url: str = "http://localhost:8000"

    # --- Google Sheets ---------------------------------------------------------
    sheets_backend: Literal["google", "fake"] = "google"
    sheets_spreadsheet_id: str | None = None
    sheets_tab_brochure: str = "Brochure Downloads"
    sheets_tab_exam: str = "Exam Registrations"
    sheets_timeout_seconds: float = 8.0
    fake_sheets_dir: str = "/var/sheets"

    # --- Internal (scheduled) endpoints ---------------------------------------
    internal_auth_mode: Literal["oidc", "token"] = "oidc"
    internal_task_token: str = ""
    internal_oidc_audience: str | None = None
    internal_allowed_service_accounts: str = ""

    # --- Exam ------------------------------------------------------------------
    exam_token_secret: str = ""
    exam_duration_minutes: int = 150
    exam_submit_grace_seconds: int = 300

    # --- Upload limits and abuse protection ------------------------------------
    max_image_upload_mb: int = 10
    max_pdf_upload_mb: int = 25
    max_excel_upload_mb: int = 5
    rate_limit_enabled: bool = True

    @property
    def is_cloud(self) -> bool:
        return self.app_env in ("staging", "production")

    @property
    def sqlalchemy_url(self) -> URL:
        if self.database_url:
            return make_url(self.database_url)
        if self.cloud_sql_connection_name:
            return URL.create(
                "postgresql+psycopg",
                username=self.db_user,
                password=self.db_password,
                database=self.db_name,
                query={"host": f"/cloudsql/{self.cloud_sql_connection_name}"},
            )
        return URL.create(
            "postgresql+psycopg",
            username=self.db_user,
            password=self.db_password,
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def allowed_internal_service_accounts(self) -> set[str]:
        return {s.strip().lower() for s in self.internal_allowed_service_accounts.split(",") if s.strip()}

    @property
    def token_secret(self) -> str:
        return self.exam_token_secret or (DEV_TOKEN_SECRET if not self.is_cloud else "")

    def validate_for_environment(self) -> None:
        """Refuse to start with unsafe settings in staging or production."""
        if self.local_dashboard_mode or self.local_firebase_auth_test_mode:
            local_problems: list[str] = []
            if self.local_dashboard_mode and self.local_firebase_auth_test_mode:
                local_problems.append("only one local dashboard mode may be enabled")
            if self.app_env != "local":
                local_problems.append("local dashboard modes are permitted only when APP_ENV is \"local\"")
            expected_auth_mode = "fake" if self.local_dashboard_mode else "firebase"
            if self.auth_mode != expected_auth_mode:
                local_problems.append(f"selected local mode requires AUTH_MODE=\"{expected_auth_mode}\"")
            if self.storage_backend != "local":
                local_problems.append('local dashboard modes require STORAGE_BACKEND="local"')
            if self.sheets_backend != "fake":
                local_problems.append('local dashboard modes require SHEETS_BACKEND="fake"')
            if self.sqlalchemy_url.get_backend_name() != "sqlite":
                local_problems.append("local dashboard modes require a SQLite DATABASE_URL")
            if self.local_firebase_auth_test_mode:
                missing = [
                    name
                    for name, value in (
                        ("GCP_PROJECT_ID", self.gcp_project_id),
                        ("FIREBASE_WEB_API_KEY", self.firebase_web_api_key),
                        ("FIREBASE_WEB_AUTH_DOMAIN", self.firebase_web_auth_domain),
                        ("FIREBASE_WEB_APP_ID", self.firebase_web_app_id),
                    )
                    if not value
                ]
                if missing:
                    local_problems.append("Firebase auth test mode requires " + ", ".join(missing))
            if local_problems:
                raise RuntimeError("Invalid local dashboard configuration: " + "; ".join(local_problems))

        if not self.is_cloud:
            return
        problems: list[str] = []
        if self.auth_mode != "firebase":
            problems.append('AUTH_MODE must be "firebase"')
        if self.storage_backend != "firebase":
            problems.append('STORAGE_BACKEND must be "firebase"')
        if not self.storage_bucket:
            problems.append("STORAGE_BUCKET is required")
        if self.sheets_backend != "google":
            problems.append('SHEETS_BACKEND must be "google"')
        if not self.sheets_spreadsheet_id:
            problems.append("SHEETS_SPREADSHEET_ID is required")
        if len(self.exam_token_secret) < 32:
            problems.append("EXAM_TOKEN_SECRET must be at least 32 characters")
        if not self.gcp_project_id:
            problems.append("GCP_PROJECT_ID is required")
        if self.internal_auth_mode == "oidc" and not (
            self.internal_oidc_audience and self.allowed_internal_service_accounts
        ):
            problems.append("INTERNAL_OIDC_AUDIENCE and INTERNAL_ALLOWED_SERVICE_ACCOUNTS are required")
        if self.internal_auth_mode == "token" and len(self.internal_task_token) < 32:
            problems.append("INTERNAL_TASK_TOKEN must be at least 32 characters")

        if problems:
            raise RuntimeError(f"Invalid configuration for {self.app_env}: {'; '.join(problems)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
