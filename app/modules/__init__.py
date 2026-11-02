"""Feature-module registry used to assemble each FastAPI service."""

from __future__ import annotations

from app.core.module import Module
from app.modules.admin_auth import module as admin_auth_module
from app.modules.announcements import module as announcements_module
from app.modules.banners import module as banners_module
from app.modules.batches import module as batches_module
from app.modules.courses import module as courses_module
from app.modules.exam import module as exam_module
from app.modules.public_site import module as public_site_module
from app.modules.registration import module as registration_module
from app.modules.site_settings import module as site_settings_module
from app.modules.videos import module as videos_module

# Keep this dependency order: a split service can select a subset, while the
# normal application mounts every existing router in a predictable order.
ALL_MODULES: tuple[Module, ...] = (
    admin_auth_module,
    registration_module,
    site_settings_module,
    courses_module,
    announcements_module,
    banners_module,
    batches_module,
    videos_module,
    exam_module,
    public_site_module,
)

_MODULES_BY_NAME = {module.name: module for module in ALL_MODULES}


def select_modules(enabled_modules: str) -> tuple[Module, ...]:
    """Return enabled modules after checking the declared dependencies.

    ``ENABLED_MODULES=all`` is the standard deployment. A comma-separated
    subset is supported for the separately scalable exam service documented in
    ``docs/01-architecture.md``.
    """

    requested = {name.strip() for name in enabled_modules.split(",") if name.strip()}
    if not requested or requested == {"all"}:
        return ALL_MODULES

    unknown = requested.difference(_MODULES_BY_NAME)
    if unknown:
        raise ValueError(f"Unknown ENABLED_MODULES entries: {', '.join(sorted(unknown))}")

    missing = [
        f"{module.name} requires {dependency}"
        for module in ALL_MODULES
        if module.name in requested
        for dependency in module.depends_on
        if dependency not in requested
    ]
    if missing:
        raise ValueError("Invalid ENABLED_MODULES: " + "; ".join(missing))

    return tuple(module for module in ALL_MODULES if module.name in requested)


__all__ = ["ALL_MODULES", "select_modules"]
