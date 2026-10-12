"""profile analysis: needs, values, personality, headline, ideal date

Revision ID: 002
Revises: 001
Create Date: 2026-10-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Same additive, idempotent upgrade the API applies on startup.
    from app.db.migrate import ensure_schema
    from app.models import *  # noqa: F401,F403

    ensure_schema(op.get_bind().engine)


def downgrade() -> None:
    pass
