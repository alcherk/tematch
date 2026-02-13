"""initial tables

Revision ID: 15f20740e572
Revises:
Create Date: 2026-02-13 18:59:31.228814

"""
from typing import Optional, Sequence, Union

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision: str = "15f20740e572"
down_revision: Optional[Union[str, Sequence[str]]] = None
branch_labels: Optional[Union[str, Sequence[str]]] = None
depends_on: Optional[Union[str, Sequence[str]]] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("interests", sa.Text(), nullable=True),
        sa.Column("digest_cron", sa.String(50), default="0 9 * * *"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("telegram_id", sa.BigInteger(), unique=True, nullable=False),
        sa.Column("username", sa.String(255), nullable=True),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("active", sa.Boolean(), default=True),
        sa.Column("last_fetched_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "user_channels",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "channel_id", sa.Integer(), sa.ForeignKey("channels.id"), nullable=False
        ),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "channel_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "channel_id", sa.Integer(), sa.ForeignKey("channels.id"), nullable=False
        ),
        sa.Column("telegram_msg_id", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("date", sa.DateTime(), nullable=True),
        sa.Column("embedding", Vector(1536), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("channel_id", "telegram_msg_id"),
    )

    op.create_table(
        "recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column(
            "message_id", sa.Integer(), sa.ForeignKey("messages.id"), nullable=False
        ),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("delivered", sa.Boolean(), default=False),
        sa.Column("feedback", sa.String(10), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("recommendations")
    op.drop_table("messages")
    op.drop_table("user_channels")
    op.drop_table("channels")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
