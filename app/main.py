"""Application entry point: ``uvicorn app.main:app``."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

import app.models  # noqa: F401 (registers every table)
from app import __version__
from app.core import health
from app.core.config import Settings, get_settings
from app.core.error import register_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import register_middleware
from app.modules import select_modules

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    settings.validate_for_environment()
    if settings.local_dashboard_mode or settings.local_firebase_auth_test_mode:
        from app.core.local_development import initialize_local_dashboard

        initialize_local_dashboard(settings, include_local_admin=settings.local_dashboard_mode)
    modules = select_modules(settings.enabled_modules)

    show_docs = settings.app_env != "production"
    application = FastAPI(
        title="College Website API",
        version=__version__,
        description="Backend for the college website. See README.md and docs/09-api-reference.md.",
        docs_url="/docs" if show_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if show_docs else None,
    )
    register_error_handlers(application)
    register_middleware(application)

    if settings.cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=[
                "Authorization",
                "Content-Type",
                "X-Firebase-AppCheck",
                "X-Request-ID",
            ],
            max_age=3600,
        )

    application.include_router(health.router, prefix="/api/v1")
    for module in modules:
        if module.public_router:
            application.include_router(module.public_router, prefix="/api/v1")
        if module.admin_router:
            application.include_router(module.admin_router, prefix="/api/v1/admin")
        if module.internal_router:
            application.include_router(module.internal_router, prefix="/internal")

    @application.get("/admin/firebase-config.js", include_in_schema=False)
    def admin_firebase_config() -> Response:
        """Expose Firebase's public web configuration to the same-origin admin SPA."""
        config = {
            "apiKey": settings.firebase_web_api_key,
            "authDomain": settings.firebase_web_auth_domain,
            "projectId": settings.gcp_project_id,
            "storageBucket": settings.storage_bucket,
            "messagingSenderId": settings.firebase_web_messaging_sender_id,
            "appId": settings.firebase_web_app_id,
            "measurementId": settings.firebase_web_measurement_id,
        }
        return Response(
            "window.__FIREBASE_CONFIG__ = " + json.dumps(config) + ";\n",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    @application.get("/admin/local-development.js", include_in_schema=False)
    def admin_local_development_config() -> Response:
        """Expose only the local-development switch; never production credentials."""
        return Response(
            "window.__LOCAL_DASHBOARD_MODE__ = "
            + json.dumps(settings.local_dashboard_mode)
            + ";\n",
            media_type="application/javascript",
            headers={"Cache-Control": "no-store"},
        )

    # The SPA has no server-side session. It requests Firebase tokens in the
    # browser and every mutable operation remains protected by FastAPI deps.
    admin_directory = Path(__file__).parent / "static" / "admin"
    application.mount("/admin", StaticFiles(directory=admin_directory, html=True), name="admin")

    if settings.storage_backend == "local":
        from app.core.storage import LocalStorage

        local_storage = LocalStorage(settings.local_storage_dir, settings.public_base_url)

        application.mount(
            "/media",
            StaticFiles(directory=local_storage.public_dir),
            name="media",
        )

    logger.info(
        "Application started",
        extra={
            "environment": settings.app_env,
            "modules": [m.name for m in modules],
            "version": __version__,
        },
    )
    return application


app = create_app()
