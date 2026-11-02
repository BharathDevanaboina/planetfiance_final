"""SQLAlchemy types for legacy PostgreSQL columns.

The existing PlanetFiance schema stores a few JSON values in ``text`` columns.
This adapter reads valid JSON into Python values and writes JSON text without
changing the underlying database column type.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class JSONText(TypeDecorator[Any]):
    """Map JSON encoded in a PostgreSQL ``text`` column to Python values.

    Legacy non-JSON values are returned unchanged.  This is deliberate: a
    failed parse must never silently replace existing content with an empty
    object or list.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: object) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

    def process_result_value(self, value: str | None, dialect: object) -> Any:
        if value is None:
            return None
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value
