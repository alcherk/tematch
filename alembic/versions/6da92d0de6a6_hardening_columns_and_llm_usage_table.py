"""hardening columns and llm_usage table

Revision ID: 6da92d0de6a6
Revises: 15f20740e572
Create Date: 2026-02-13 19:25:34.163284

"""
from typing import Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6da92d0de6a6"
down_revision: Union[str, Sequence[str], None] = "15f20740e572"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users: last_digest_at, interests_embedding ---
    op.add_column("users", sa.Column("last_digest_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("interests_embedding", Vector(1536), nullable=True))

    # --- messages: content_hash ---
    op.add_column("messages", sa.Column("content_hash", sa.String(64), nullable=True))
    op.create_index("ix_messages_content_hash", "messages", ["content_hash"])

    # Backfill content_hash for existing messages using SHA-256 of normalized text
    # Must match Python normalization: lower + collapse whitespace + strip
    op.execute(
        """
        UPDATE messages
        SET content_hash = encode(
            sha256(
                convert_to(
                    regexp_replace(lower(trim(text)), '\\s+', ' ', 'g'),
                    'UTF8'
                )
            ),
            'hex'
        )
        WHERE content_hash IS NULL
        """
    )

    # --- llm_usage table ---
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("operation", sa.String(50), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_estimate", sa.Float(), server_default="0.0"),
    )
    op.create_index("ix_llm_usage_date", "llm_usage", ["date"])


def downgrade() -> None:
    op.drop_index("ix_llm_usage_date", table_name="llm_usage")
    op.drop_table("llm_usage")

    op.drop_index("ix_messages_content_hash", table_name="messages")
    op.drop_column("messages", "content_hash")

    op.drop_column("users", "interests_embedding")
    op.drop_column("users", "last_digest_at")
