"""add text_html to messages

Revision ID: b4c2d3e5f6a7
Revises: a3b1c2d3e4f5
Create Date: 2026-02-14 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c2d3e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a3b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("text_html", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "text_html")
