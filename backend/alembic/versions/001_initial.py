"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Tables are also created via SQLAlchemy metadata on startup.
    # This revision documents the baseline for PostgreSQL deployments.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("participants"):
        from app.db.base import Base
        from app.models import *  # noqa: F401,F403

        Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass
