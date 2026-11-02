"""Add the Firebase-backed administrator allow-list.

This revision is intentionally separate from the original ``0001`` migration.
It creates only ``public.admin_users`` and never changes existing PlanetFiance
tables.  It must be applied only after the existing production schema has been
baselined (stamped) at revision ``20261102_0001_planetfiance_baseline``; do
not run legacy revision ``0001`` against the already-populated production
database.

Revision ID: 20261102_0002
Revises: 20261102_0001_planetfiance_baseline
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261102_0002"
down_revision: str | None = "20261102_0001_planetfiance_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE_NAME = "admin_users"
EXPECTED_COLUMNS = {
    "id",
    "singleton_key",
    "firebase_uid",
    "email",
    "full_name",
    "is_active",
    "last_login_at",
    "created_at",
    "updated_at",
}
EXPECTED_NULLABILITY = {
    "id": False,
    "singleton_key": False,
    "firebase_uid": False,
    "email": False,
    "full_name": True,
    "is_active": False,
    "last_login_at": True,
    "created_at": False,
    "updated_at": False,
}
EXPECTED_DEFAULTS = {
    "id": None,
    "singleton_key": "1",
    "firebase_uid": None,
    "email": None,
    "full_name": None,
    "is_active": "true",
    "last_login_at": None,
    "created_at": "now()",
    "updated_at": "now()",
}
EXPECTED_UNIQUES = {
    ("uq_admin_users_singleton_key", ("singleton_key",)),
    ("uq_admin_users_firebase_uid", ("firebase_uid",)),
    ("uq_admin_users_email", ("email",)),
}


def _normalized_default(value: object | None) -> str | None:
    """Normalize PostgreSQL inspector formatting, not the default's meaning."""
    if value is None:
        return None
    return re.sub(r"::(?:smallint|boolean)", "", "".join(str(value).lower().split()))


def _has_expected_type(column: dict[str, object]) -> bool:
    column_type = column["type"]
    name = column["name"]
    if name == "id":
        return isinstance(column_type, sa.Uuid)
    if name == "singleton_key":
        return isinstance(column_type, sa.SmallInteger)
    if name in {"firebase_uid", "email", "full_name"}:
        expected_length = {"firebase_uid": 128, "email": 320, "full_name": 120}[name]
        return isinstance(column_type, sa.String) and column_type.length == expected_length
    if name == "is_active":
        return isinstance(column_type, sa.Boolean)
    return isinstance(column_type, sa.DateTime) and column_type.timezone is True


def _has_exact_structure(inspector: sa.Inspector) -> bool:
    columns = {column["name"]: column for column in inspector.get_columns(TABLE_NAME, schema="public")}
    if set(columns) != EXPECTED_COLUMNS:
        return False
    if any(
        column["nullable"] != EXPECTED_NULLABILITY[name]
        or _normalized_default(column.get("default")) != EXPECTED_DEFAULTS[name]
        or not _has_expected_type(column)
        for name, column in columns.items()
    ):
        return False

    primary_key = inspector.get_pk_constraint(TABLE_NAME, schema="public")
    if primary_key.get("name") != "pk_admin_users" or tuple(primary_key.get("constrained_columns") or ()) != (
        "id",
    ):
        return False

    uniques = {
        (constraint.get("name"), tuple(constraint.get("column_names") or ()))
        for constraint in inspector.get_unique_constraints(TABLE_NAME, schema="public")
    }
    if uniques != EXPECTED_UNIQUES:
        return False

    checks = {
        (constraint.get("name"), re.sub(r"[\s()]", "", constraint.get("sqltext", "").lower()))
        for constraint in inspector.get_check_constraints(TABLE_NAME, schema="public")
    }
    if checks != {("ck_admin_users_singleton_key_one", "singleton_key=1")}:
        return False

    # This migration creates no foreign keys or standalone indexes. Indexes
    # backing named unique constraints are ignored by dialect inspection.
    if inspector.get_foreign_keys(TABLE_NAME, schema="public"):
        return False
    return not any(
        not index.get("duplicates_constraint") for index in inspector.get_indexes(TABLE_NAME, schema="public")
    )


def upgrade() -> None:
    """Create the standalone admin allow-list, failing closed on a conflict."""
    bind = op.get_bind()
    if sa.inspect(bind).has_table(TABLE_NAME, schema="public"):
        raise RuntimeError(
            "Refusing to create public.admin_users because it already exists. "
            "Inspect its schema before marking this migration as applied."
        )

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("singleton_key", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("firebase_uid", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admin_users"),
        sa.CheckConstraint("singleton_key = 1", name="ck_admin_users_singleton_key_one"),
        sa.UniqueConstraint("singleton_key", name="uq_admin_users_singleton_key"),
        sa.UniqueConstraint("firebase_uid", name="uq_admin_users_firebase_uid"),
        sa.UniqueConstraint("email", name="uq_admin_users_email"),
        schema="public",
    )


def downgrade() -> None:
    """Remove only the table created by this revision after a shape check."""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME, schema="public"):
        return

    if not _has_exact_structure(inspector):
        raise RuntimeError(
            "Refusing to drop public.admin_users because its complete structure no longer "
            "matches the table created by revision 20261102_0002."
        )

    op.drop_table(TABLE_NAME, schema="public")
