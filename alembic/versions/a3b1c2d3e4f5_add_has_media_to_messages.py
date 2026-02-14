"""add has_media to messages

Revision ID: a3b1c2d3e4f5
Revises: 6da92d0de6a6
Create Date: 2026-02-14 16:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a3b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "6da92d0de6a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("has_media", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("messages", "has_media")
