"""Additive schema upgrades for databases created before a column existed.

Tables are created with ``Base.metadata.create_all``, which never alters an
existing table, so new nullable columns are added here on startup.
"""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from app.db.base import Base

# table -> {column: DDL type}
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "profile_analyses": {
        "headline": "VARCHAR(400)",
        "needs": "JSON",
        "core_values": "JSON",
        "personality_traits": "JSON",
        "ideal_date": "TEXT",
    },
}


def ensure_schema(engine: Engine) -> None:
    """Create missing tables, then add any columns introduced after first deploy."""
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    for table, columns in _ADDED_COLUMNS.items():
        existing = {c["name"] for c in inspector.get_columns(table)}
        missing = {name: ddl for name, ddl in columns.items() if name not in existing}
        if not missing:
            continue
        with engine.begin() as connection:
            for name, ddl in missing.items():
                connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
