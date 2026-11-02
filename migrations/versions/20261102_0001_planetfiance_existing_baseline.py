"""Baseline marker for the existing PlanetFiance singular-table schema.

This is intentionally a no-op revision.  It documents the verified production
schema so an existing database can be recorded in Alembic *without* replaying
the legacy ``0001`` migration, which describes a different plural-table
schema.  It never creates, alters, renames or drops a table.

Revision ID: 20261102_0001_planetfiance_baseline
Revises: None
Branch labels: planetfiance_existing
"""

from collections.abc import Sequence

revision: str = "20261102_0001_planetfiance_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = ("planetfiance_existing",)
depends_on: str | Sequence[str] | None = None

# Verified from the read-only information_schema and constraints exports.  This
# manifest is documentation only; Alembic does not execute it as DDL.
EXISTING_SCHEMA = {
    "course": {"primary_key": ("code",)},
    "batch": {"primary_key": ("id",), "foreign_keys": {"course_code": "course.code"}},
    "banner": {"primary_key": ("id",), "foreign_keys": {"course_code": "course.code"}},
    "announcement": {"primary_key": ("id",)},
    "site_setting": {"primary_key": ("id",)},
    "video": {"primary_key": ("id",)},
    "exam_set": {"primary_key": ("slot",)},
    "exam_passage": {"primary_key": ("id",), "foreign_keys": {"exam_set_slot": "exam_set.slot"}},
    "exam_question": {
        "primary_key": ("id",),
        "foreign_keys": {
            "exam_set_slot": "exam_set.slot",
            "passage_id": "exam_passage.id",
        },
    },
    "exam_option": {"primary_key": ("id",), "foreign_keys": {"question_id": "exam_question.id"}},
}


def upgrade() -> None:
    """No-op: existing PlanetFiance tables are intentionally left untouched."""


def downgrade() -> None:
    """No-op: removing a baseline marker must not change production schema."""
