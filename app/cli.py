"""Command-line tasks for operators.

Run ``python -m app.cli --help``.
(See docs/08-operations.md). In the cloud these run as a Cloud Run job.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.core.database import get_session_factory


def _db():
    return get_session_factory()()


def cmd_grant_existing_admin(args: argparse.Namespace) -> int:
    """Initialize the sole allow-list entry from a verified Firebase user."""
    if get_settings().auth_mode != "firebase":
        raise RuntimeError("grant-existing-admin requires AUTH_MODE=firebase.")

    # Initialises Firebase Admin using the runtime identity, then performs a
    # read-only lookup.  No Firebase user is created, updated or reset here.
    from app.core.dependencies import get_identity_verifier

    get_identity_verifier()
    from firebase_admin import auth

    from app.modules.admin_auth import service

    firebase_user = auth.get_user_by_email(args.email)
    if not firebase_user.email_verified:
        raise ValueError("The Firebase account email must be verified before admin access is granted.")
    if not any(provider.provider_id == "google.com" for provider in firebase_user.provider_data):
        raise ValueError("The Firebase account must be an existing Google Sign-In account.")
    with _db() as db:
        admin = service.initialize_admin(
            db,
            firebase_user.uid,
            firebase_user.email or args.email,
            args.name or firebase_user.display_name,
        )
    print(f"The sole admin was registered: {admin.email} (Firebase UID verified server-side).")
    return 0


def cmd_list_admins(_: argparse.Namespace) -> int:
    from app.modules.admin_auth import service

    with _db() as db:
        for admin in service.list_admins(db):
            state = "active" if admin.is_active else "inactive"
            print(f"{admin.email:40} {state:9} last login: {admin.last_login_at}")
    return 0


def cmd_generate_exam_template(args: argparse.Namespace) -> int:
    from app.modules.exam.template import build_template

    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_template())
    print(f"Template written to {target}")
    return 0


def cmd_validate_exam_file(args: argparse.Namespace) -> int:
    from app.modules.exam.service import validate_file

    report = validate_file(Path(args.file).read_bytes())
    print(report.model_dump_json(indent=2))
    return 0 if report.ok else 1


def cmd_check_config(_: argparse.Namespace) -> int:
    settings = get_settings()
    settings.validate_for_environment()
    from app.modules import select_modules

    modules = [m.name for m in select_modules(settings.enabled_modules)]
    print(f"Environment: {settings.app_env}\nModules: {', '.join(modules)}\nConfiguration looks valid.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli", description="College backend operator commands"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "grant-existing-admin",
        help="One-time registration of an existing verified Firebase administrator",
    )
    p.add_argument("--email", required=True)
    p.add_argument("--name")
    p.set_defaults(func=cmd_grant_existing_admin)

    sub.add_parser("list-admins", help="List admin accounts").set_defaults(func=cmd_list_admins)
    p = sub.add_parser("generate-exam-template", help="Write the Excel template for question sets")
    p.add_argument("--output", default="templates/exam-question-set-template.xlsx")
    p.set_defaults(func=cmd_generate_exam_template)

    p = sub.add_parser("validate-exam-file", help="Check a question-set Excel file without uploading it")
    p.add_argument("file")
    p.set_defaults(func=cmd_validate_exam_file)

    sub.add_parser("check-config", help="Validate the current configuration").set_defaults(
        func=cmd_check_config
    )

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
