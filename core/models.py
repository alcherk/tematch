# core/models.py
from __future__ import annotations

import datetime as dt
from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Float,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    interests: Mapped[Optional[str]] = mapped_column(Text)
    digest_cron: Mapped[Optional[str]] = mapped_column(String(50), default="0 9 * * *")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_digest_at: Mapped[Optional[datetime]] = mapped_column()
    interests_embedding = mapped_column(Vector(1536), nullable=True)

    channels = relationship("UserChannel", back_populates="user")
    recommendations = relationship("Recommendation", back_populates="user")

    def __init__(self, **kwargs):
        kwargs.setdefault("digest_cron", "0 9 * * *")
        super().__init__(**kwargs)


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    title: Mapped[Optional[str]] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    users = relationship("UserChannel", back_populates="channel")
    messages = relationship("Message", back_populates="channel")


class UserChannel(Base):
    __tablename__ = "user_channels"
    __table_args__ = (UniqueConstraint("user_id", "channel_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    added_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user = relationship("User", back_populates="channels")
    channel = relationship("Channel", back_populates="users")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("channel_id", "telegram_msg_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channels.id"))
    telegram_msg_id: Mapped[int] = mapped_column(nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    reply_to_msg_id: Mapped[Optional[int]] = mapped_column(index=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[Optional[datetime]] = mapped_column()
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    channel = relationship("Channel", back_populates="messages")
    recommendations = relationship("Recommendation", back_populates="message")


class Recommendation(Base):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"))
    score: Mapped[float] = mapped_column(Float, nullable=False)
    delivered: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[Optional[str]] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user = relationship("User", back_populates="recommendations")
    message = relationship("Message", back_populates="recommendations")

    def __init__(self, **kwargs):
        kwargs.setdefault("delivered", False)
        super().__init__(**kwargs)


class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_in: Mapped[int] = mapped_column(nullable=False)
    tokens_out: Mapped[int] = mapped_column(nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
