# Tematch Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a two-process Telegram bot that collects channel messages via Telethon, stores embeddings in PostgreSQL+pgvector, and delivers personalized recommendations via aiogram.

**Architecture:** Collector (Telethon) writes messages+embeddings to PostgreSQL. Bot (aiogram) reads from DB, runs two-stage recommendation (pgvector similarity → LLM ranking), delivers digests. Processes share nothing except the database.

**Tech Stack:** Python 3.9+, aiogram 3, Telethon, SQLAlchemy 2 async, asyncpg, pgvector, APScheduler, Pydantic Settings

**Design doc:** `docs/plans/2026-02-13-architecture-design.md`

---

### Task 1: Infrastructure — Docker, requirements, config

**Files:**
- Create: `requirements.txt`
- Create: `requirements-dev.txt`
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `Dockerfile`
- Create: `core/__init__.py`
- Create: `core/config.py`
- Test: `tests/__init__.py`
- Test: `tests/test_config.py`

**Step 1: Create requirements.txt**

```
# Telegram
aiogram>=3.0,<4.0
telethon>=1.34,<2.0

# Database
sqlalchemy[asyncio]>=2.0,<3.0
asyncpg>=0.29
alembic>=1.13
pgvector>=0.3

# LLM
anthropic>=0.40
openai>=1.50
tiktoken>=0.7

# Scheduling
apscheduler>=3.10,<4.0

# Config & Utils
pydantic-settings>=2.0
python-dotenv>=1.0
```

**Step 2: Create requirements-dev.txt**

```
-r requirements.txt
pytest>=8.0
pytest-asyncio>=0.24
pytest-cov>=5.0
```

**Step 3: Create .env.example**

```
# Telegram
TG_API_ID=your_api_id
TG_API_HASH=your_api_hash
TG_BOT_TOKEN=your_bot_token
TG_SESSION_NAME=tematch_collector

# Database
DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch
DB_PASSWORD=tematch

# LLM
LLM_PROVIDER=openai
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Recommender
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
CANDIDATES_LIMIT=50
DIGEST_SIZE=5

# Scheduler
DEFAULT_DIGEST_CRON=0 9 * * *
```

**Step 4: Create docker-compose.yml**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: tematch
      POSTGRES_USER: tematch
      POSTGRES_PASSWORD: ${DB_PASSWORD:-tematch}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U tematch"]
      interval: 5s
      timeout: 5s
      retries: 5

  collector:
    build: .
    command: python -m collector.main
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env
    volumes:
      - ./sessions:/app/sessions

  bot:
    build: .
    command: python -m bot.main
    depends_on:
      postgres:
        condition: service_healthy
    env_file: .env

volumes:
  pgdata:
```

**Step 5: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "bot.main"]
```

**Step 6: Write the failing test for config**

```python
# tests/test_config.py
import os
import pytest
from core.config import Settings


def test_settings_loads_defaults():
    settings = Settings(
        TG_API_ID=123,
        TG_API_HASH="abc",
        TG_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert settings.LLM_PROVIDER == "openai"
    assert settings.EMBEDDING_DIM == 1536
    assert settings.CANDIDATES_LIMIT == 50
    assert settings.DIGEST_SIZE == 5
    assert settings.DEFAULT_DIGEST_CRON == "0 9 * * *"


def test_settings_requires_telegram_fields():
    with pytest.raises(Exception):
        Settings(DATABASE_URL="postgresql+asyncpg://localhost/test")
```

**Step 7: Run test to verify it fails**

Run: `cd /Users/lex/Projects/personal/Tematch && venv/bin/pip install -r requirements-dev.txt && venv/bin/pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.config'`

**Step 8: Implement config**

```python
# core/__init__.py
# (empty)

# core/config.py
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    TG_API_ID: int
    TG_API_HASH: str
    TG_BOT_TOKEN: str
    TG_SESSION_NAME: str = "tematch_collector"

    # Database
    DATABASE_URL: str

    # LLM
    LLM_PROVIDER: str = "openai"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Recommender
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    CANDIDATES_LIMIT: int = 50
    DIGEST_SIZE: int = 5

    # Scheduler
    DEFAULT_DIGEST_CRON: str = "0 9 * * *"

    model_config = {"env_file": ".env", "extra": "ignore"}
```

**Step 9: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_config.py -v`
Expected: PASS (2 tests)

**Step 10: Commit**

```bash
git add requirements.txt requirements-dev.txt .env.example docker-compose.yml Dockerfile core/ tests/
git commit -m "feat: add project infrastructure — config, Docker, dependencies"
```

---

### Task 2: Database — Models and migrations

**Files:**
- Create: `core/db.py`
- Create: `core/models.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Test: `tests/test_models.py`

**Step 1: Write the failing test for models**

```python
# tests/test_models.py
from core.models import User, Channel, UserChannel, Message, Recommendation


def test_user_model_has_fields():
    u = User(telegram_id=123, interests="ML and crypto")
    assert u.telegram_id == 123
    assert u.interests == "ML and crypto"
    assert u.digest_cron == "0 9 * * *"


def test_channel_model_has_fields():
    c = Channel(telegram_id=456, username="test_channel", title="Test")
    assert c.telegram_id == 456
    assert c.username == "test_channel"


def test_message_model_has_fields():
    m = Message(channel_id=1, telegram_msg_id=100, text="Hello world")
    assert m.text == "Hello world"
    assert m.embedding is None


def test_recommendation_model_has_fields():
    r = Recommendation(user_id=1, message_id=1, score=0.95)
    assert r.score == 0.95
    assert r.delivered is False
    assert r.feedback is None
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.models'`

**Step 3: Implement db.py**

```python
# core/db.py
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine, AsyncSession
from core.config import Settings


def create_engine(settings: Settings):
    return create_async_engine(settings.DATABASE_URL, echo=False)


def create_session_factory(engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

**Step 4: Implement models.py**

```python
# core/models.py
from datetime import datetime
from sqlalchemy import BigInteger, Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    interests: Mapped[str | None] = mapped_column(Text)
    digest_cron: Mapped[str] = mapped_column(String(50), default="0 9 * * *")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    channels = relationship("UserChannel", back_populates="user")
    recommendations = relationship("Recommendation", back_populates="user")


class Channel(Base):
    __tablename__ = "channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str | None] = mapped_column(String(255))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[datetime | None] = mapped_column()
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
    date: Mapped[datetime | None] = mapped_column()
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
    feedback: Mapped[str | None] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user = relationship("User", back_populates="recommendations")
    message = relationship("Message", back_populates="recommendations")
```

**Step 5: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_models.py -v`
Expected: PASS (4 tests)

**Step 6: Initialize Alembic**

Run: `cd /Users/lex/Projects/personal/Tematch && venv/bin/alembic init alembic`

Then edit `alembic/env.py` to use async engine and import models:

```python
# alembic/env.py — key changes:
# 1. import core.models.Base for target_metadata
# 2. use async engine from DATABASE_URL env var
# 3. run_async_migrations() pattern
```

Edit `alembic.ini`:
```
sqlalchemy.url = postgresql+asyncpg://tematch:tematch@localhost:5432/tematch
```

**Step 7: Generate initial migration**

Run: `venv/bin/alembic revision --autogenerate -m "initial tables"`

**Step 8: Start PostgreSQL and apply migration**

Run: `docker compose up -d postgres && sleep 3 && venv/bin/alembic upgrade head`

**Step 9: Commit**

```bash
git add core/db.py core/models.py alembic/ alembic.ini tests/test_models.py
git commit -m "feat: add database models and Alembic migrations"
```

---

### Task 3: LLM Abstraction — Base + OpenAI + Claude

**Files:**
- Create: `core/llm/__init__.py`
- Create: `core/llm/base.py`
- Create: `core/llm/openai_provider.py`
- Create: `core/llm/claude_provider.py`
- Create: `core/embeddings.py`
- Test: `tests/test_llm.py`
- Test: `tests/test_embeddings.py`

**Step 1: Write the failing test for LLM base**

```python
# tests/test_llm.py
import pytest
from core.llm.base import LLMProvider, create_llm_provider


def test_create_openai_provider():
    provider = create_llm_provider("openai", api_key="test-key")
    assert isinstance(provider, LLMProvider)


def test_create_claude_provider():
    provider = create_llm_provider("claude", api_key="test-key")
    assert isinstance(provider, LLMProvider)


def test_create_unknown_provider_raises():
    with pytest.raises(ValueError, match="Unknown LLM provider"):
        create_llm_provider("unknown", api_key="test")
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_llm.py -v`
Expected: FAIL

**Step 3: Implement LLM abstraction**

```python
# core/llm/__init__.py
from core.llm.base import LLMProvider, create_llm_provider

# core/llm/base.py
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> list[dict]:
        """Rank messages by relevance. Returns [{"message_id": ..., "score": ...}]."""
        ...


def create_llm_provider(provider: str, api_key: str) -> LLMProvider:
    if provider == "openai":
        from core.llm.openai_provider import OpenAIProvider
        return OpenAIProvider(api_key=api_key)
    elif provider == "claude":
        from core.llm.claude_provider import ClaudeProvider
        return ClaudeProvider(api_key=api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


# core/llm/openai_provider.py
from openai import AsyncOpenAI
import json
from core.llm.base import LLMProvider

RANK_PROMPT = """You are a content recommendation engine.
Given a user's interests and a list of messages, rank the messages by relevance.

User interests: {interests}

Messages:
{messages}

Return a JSON array of the top {limit} message IDs sorted by relevance, with scores 0-1:
[{{"message_id": 1, "score": 0.95}}, ...]
Return ONLY the JSON array, no other text."""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> list[dict]:
        msg_text = "\n".join(
            f"[ID={m['id']}] {m['text'][:300]}" for m in messages
        )
        prompt = RANK_PROMPT.format(
            interests=user_interests, messages=msg_text, limit=limit
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)


# core/llm/claude_provider.py
from anthropic import AsyncAnthropic
import json
from core.llm.base import LLMProvider
from core.llm.openai_provider import RANK_PROMPT


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> list[dict]:
        msg_text = "\n".join(
            f"[ID={m['id']}] {m['text'][:300]}" for m in messages
        )
        prompt = RANK_PROMPT.format(
            interests=user_interests, messages=msg_text, limit=limit
        )
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return json.loads(response.content[0].text)
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_llm.py -v`
Expected: PASS (3 tests)

**Step 5: Write the failing test for embeddings**

```python
# tests/test_embeddings.py
import pytest
from unittest.mock import AsyncMock, patch
from core.embeddings import EmbeddingService


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = AsyncMock(
        data=[AsyncMock(embedding=[0.1] * 1536)]
    )
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = mock_client
    service.model = "text-embedding-3-small"
    service.dim = 1536

    result = await service.embed_text("hello world")
    assert len(result) == 1536
    assert result[0] == 0.1


@pytest.mark.asyncio
async def test_embed_texts_batch():
    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = AsyncMock(
        data=[
            AsyncMock(embedding=[0.1] * 1536),
            AsyncMock(embedding=[0.2] * 1536),
        ]
    )
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = mock_client
    service.model = "text-embedding-3-small"
    service.dim = 1536

    result = await service.embed_texts(["hello", "world"])
    assert len(result) == 2
```

**Step 6: Implement embeddings**

```python
# core/embeddings.py
from openai import AsyncOpenAI


class EmbeddingService:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dim = dim

    async def embed_text(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dim
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [d.embedding for d in response.data]
```

**Step 7: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_embeddings.py -v`
Expected: PASS (2 tests)

**Step 8: Commit**

```bash
git add core/llm/ core/embeddings.py tests/test_llm.py tests/test_embeddings.py
git commit -m "feat: add LLM abstraction and embedding service"
```

---

### Task 4: Recommender — Two-stage pipeline

**Files:**
- Create: `core/recommender.py`
- Test: `tests/test_recommender.py`

**Step 1: Write the failing test**

```python
# tests/test_recommender.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.recommender import Recommender


@pytest.mark.asyncio
async def test_recommend_calls_embedding_then_llm():
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_embedding.embed_text.return_value = [0.1] * 1536
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = [
        {"message_id": 1, "score": 0.95},
        {"message_id": 2, "score": 0.80},
    ]

    # Mock DB query result
    mock_result = MagicMock()
    mock_msg1 = MagicMock(id=1, text="ML news", channel_id=1)
    mock_msg2 = MagicMock(id=2, text="Crypto update", channel_id=1)
    mock_msg3 = MagicMock(id=3, text="Cat video", channel_id=2)
    mock_result.scalars.return_value.all.return_value = [mock_msg1, mock_msg2, mock_msg3]
    mock_session.execute.return_value = mock_result

    recommender = Recommender(
        embedding_service=mock_embedding,
        llm_provider=mock_llm,
        candidates_limit=50,
        digest_size=2,
    )

    results = await recommender.recommend(
        session=mock_session,
        user_id=1,
        interests="ML and crypto",
        channel_ids=[1, 2],
    )

    mock_embedding.embed_text.assert_called_once_with("ML and crypto")
    mock_llm.rank_messages.assert_called_once()
    assert len(results) == 2
    assert results[0]["message_id"] == 1
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_recommender.py -v`
Expected: FAIL

**Step 3: Implement recommender**

```python
# core/recommender.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import Message
from core.llm.base import LLMProvider
from core.embeddings import EmbeddingService


class Recommender:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_provider: LLMProvider,
        candidates_limit: int = 50,
        digest_size: int = 5,
    ):
        self.embedding_service = embedding_service
        self.llm_provider = llm_provider
        self.candidates_limit = candidates_limit
        self.digest_size = digest_size

    async def recommend(
        self,
        session: AsyncSession,
        user_id: int,
        interests: str,
        channel_ids: list[int],
    ) -> list[dict]:
        # Stage 1: pgvector similarity search
        query_vector = await self.embedding_service.embed_text(interests)

        stmt = (
            select(Message)
            .where(Message.channel_id.in_(channel_ids))
            .where(Message.embedding.isnot(None))
            .order_by(Message.embedding.cosine_distance(query_vector))
            .limit(self.candidates_limit)
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            return []

        # Stage 2: LLM ranking
        messages_for_llm = [
            {"id": m.id, "text": m.text} for m in candidates
        ]
        ranked = await self.llm_provider.rank_messages(
            messages=messages_for_llm,
            user_interests=interests,
            limit=self.digest_size,
        )

        return ranked
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_recommender.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add core/recommender.py tests/test_recommender.py
git commit -m "feat: add two-stage recommender (pgvector + LLM)"
```

---

### Task 5: Collector — Telethon message collector

**Files:**
- Create: `collector/__init__.py`
- Create: `collector/main.py`
- Create: `collector/handlers.py`
- Create: `collector/channel_manager.py`
- Test: `tests/test_collector.py`

**Step 1: Write the failing test for channel_manager**

```python
# tests/test_collector.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from collector.channel_manager import get_active_channel_ids


@pytest.mark.asyncio
async def test_get_active_channel_ids():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [100, 200, 300]
    mock_session.execute.return_value = mock_result

    ids = await get_active_channel_ids(mock_session)
    assert ids == [100, 200, 300]
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_collector.py -v`
Expected: FAIL

**Step 3: Implement collector**

```python
# collector/__init__.py
# (empty)

# collector/channel_manager.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import Channel


async def get_active_channel_ids(session: AsyncSession) -> list[int]:
    stmt = select(Channel.telegram_id).where(Channel.active.is_(True))
    result = await session.execute(stmt)
    return result.scalars().all()


# collector/handlers.py
import logging
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import Channel, Message
from core.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


async def handle_new_message(
    session: AsyncSession,
    embedding_service: EmbeddingService,
    channel_telegram_id: int,
    message_id: int,
    text: str,
    date: datetime,
):
    if not text or len(text.strip()) < 20:
        return

    # Find channel in DB
    stmt = select(Channel).where(Channel.telegram_id == channel_telegram_id)
    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        return

    # Check if message already exists
    exists_stmt = select(Message.id).where(
        Message.channel_id == channel.id,
        Message.telegram_msg_id == message_id,
    )
    exists = (await session.execute(exists_stmt)).scalar_one_or_none()
    if exists:
        return

    # Generate embedding
    try:
        embedding = await embedding_service.embed_text(text)
    except Exception as e:
        logger.error(f"Embedding failed for message {message_id}: {e}")
        embedding = None

    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        date=date,
        embedding=embedding,
    )
    session.add(msg)
    await session.commit()

    channel.last_fetched_at = datetime.utcnow()
    await session.commit()


# collector/main.py
import asyncio
import logging
from telethon import TelegramClient, events
from core.config import Settings
from core.db import create_engine, create_session_factory
from core.embeddings import EmbeddingService
from collector.handlers import handle_new_message
from collector.channel_manager import get_active_channel_ids

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    settings = Settings()
    engine = create_engine(settings)
    SessionFactory = create_session_factory(engine)

    embedding_service = EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dim=settings.EMBEDDING_DIM,
    )

    client = TelegramClient(
        settings.TG_SESSION_NAME,
        settings.TG_API_ID,
        settings.TG_API_HASH,
    )

    @client.on(events.NewMessage)
    async def on_new_message(event):
        if not event.is_channel:
            return

        chat = await event.get_chat()

        async with SessionFactory() as session:
            # Check if this channel is tracked
            active_ids = await get_active_channel_ids(session)
            if chat.id not in active_ids:
                return

            await handle_new_message(
                session=session,
                embedding_service=embedding_service,
                channel_telegram_id=chat.id,
                message_id=event.id,
                text=event.raw_text,
                date=event.date,
            )

    await client.start()
    logger.info("Collector started. Listening for channel messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_collector.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add collector/ tests/test_collector.py
git commit -m "feat: add Telethon collector for channel messages"
```

---

### Task 6: Bot — aiogram handlers

**Files:**
- Create: `bot/__init__.py`
- Create: `bot/main.py`
- Create: `bot/handlers/__init__.py`
- Create: `bot/handlers/start.py`
- Create: `bot/handlers/channels.py`
- Create: `bot/handlers/digest.py`
- Create: `bot/handlers/settings.py`
- Create: `bot/keyboards.py`
- Test: `tests/test_bot_handlers.py`

**Step 1: Write failing test for keyboard generation**

```python
# tests/test_bot_handlers.py
from bot.keyboards import feedback_keyboard, channel_actions_keyboard


def test_feedback_keyboard_has_like_dislike():
    kb = feedback_keyboard(recommendation_id=42)
    buttons = kb.inline_keyboard[0]
    assert len(buttons) == 2
    assert "like" in buttons[0].callback_data
    assert "dislike" in buttons[1].callback_data


def test_channel_actions_keyboard():
    kb = channel_actions_keyboard()
    assert len(kb.inline_keyboard) > 0
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_bot_handlers.py -v`
Expected: FAIL

**Step 3: Implement keyboards**

```python
# bot/__init__.py
# (empty)

# bot/keyboards.py
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def feedback_keyboard(recommendation_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="👍", callback_data=f"fb:like:{recommendation_id}"),
        InlineKeyboardButton(text="👎", callback_data=f"fb:dislike:{recommendation_id}"),
    ]])


def channel_actions_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Мои каналы", callback_data="channels:list"),
        InlineKeyboardButton(text="Добавить канал", callback_data="channels:add"),
    ]])
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_bot_handlers.py -v`
Expected: PASS

**Step 5: Implement bot handlers**

```python
# bot/handlers/__init__.py
# (empty)

# bot/handlers/start.py
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        user = User(telegram_id=message.from_user.id)
        session.add(user)
        await session.commit()
        await message.answer(
            "Привет! Я Tematch — подберу интересные сообщения из твоих каналов.\n\n"
            "Для начала:\n"
            "1. Перешли мне сообщение из канала или отправь @channel_name\n"
            "2. Настрой интересы: /interests\n"
            "3. Получи рекомендации: /digest"
        )
    else:
        await message.answer(
            "С возвращением! Используй /digest для рекомендаций "
            "или перешли сообщение для добавления канала."
        )


# bot/handlers/channels.py
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import Channel, UserChannel, User

router = Router()


@router.message(F.forward_from_chat)
async def handle_forwarded(message: Message, session: AsyncSession):
    chat = message.forward_from_chat
    if chat.type != "channel":
        await message.answer("Это не канал. Перешли сообщение из канала.")
        return

    user = await _get_or_create_user(session, message.from_user.id)
    channel = await _get_or_create_channel(session, chat.id, chat.username, chat.title)
    await _link_user_channel(session, user.id, channel.id)
    await message.answer(f"Канал «{chat.title}» добавлен!")


@router.message(F.text.startswith("@"))
async def handle_channel_username(message: Message, session: AsyncSession):
    username = message.text.strip().lstrip("@")
    if not username:
        await message.answer("Отправь @username канала.")
        return

    user = await _get_or_create_user(session, message.from_user.id)
    channel = await _get_or_create_channel(session, telegram_id=0, username=username, title=username)
    await _link_user_channel(session, user.id, channel.id)
    await message.answer(f"Канал @{username} добавлен! Collector начнёт сбор при следующем цикле.")


async def _get_or_create_user(session: AsyncSession, telegram_id: int) -> User:
    stmt = select(User).where(User.telegram_id == telegram_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        user = User(telegram_id=telegram_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


async def _get_or_create_channel(
    session: AsyncSession, telegram_id: int, username: str | None, title: str | None
) -> Channel:
    if telegram_id:
        stmt = select(Channel).where(Channel.telegram_id == telegram_id)
    else:
        stmt = select(Channel).where(Channel.username == username)
    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        channel = Channel(telegram_id=telegram_id, username=username, title=title)
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
    return channel


async def _link_user_channel(session: AsyncSession, user_id: int, channel_id: int):
    stmt = select(UserChannel).where(
        UserChannel.user_id == user_id, UserChannel.channel_id == channel_id
    )
    result = await session.execute(stmt)
    if not result.scalar_one_or_none():
        session.add(UserChannel(user_id=user_id, channel_id=channel_id))
        await session.commit()


# bot/handlers/digest.py
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User, UserChannel, Recommendation
from core.recommender import Recommender
from bot.keyboards import feedback_keyboard

router = Router()


@router.message(Command("digest"))
async def cmd_digest(message: Message, session: AsyncSession, recommender: Recommender):
    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    if not user.interests:
        await message.answer("Сначала настрой интересы: /interests <описание>")
        return

    # Get user's channel IDs
    ch_stmt = select(UserChannel.channel_id).where(UserChannel.user_id == user.id)
    channel_ids = (await session.execute(ch_stmt)).scalars().all()
    if not channel_ids:
        await message.answer("Добавь каналы: перешли сообщение из канала или отправь @channel_name")
        return

    await message.answer("Подбираю рекомендации...")

    ranked = await recommender.recommend(
        session=session,
        user_id=user.id,
        interests=user.interests,
        channel_ids=list(channel_ids),
    )

    if not ranked:
        await message.answer("Пока нет сообщений для рекомендаций. Подожди, пока collector соберёт контент.")
        return

    for item in ranked:
        from core.models import Message as MsgModel
        msg = await session.get(MsgModel, item["message_id"])
        if not msg:
            continue

        rec = Recommendation(
            user_id=user.id, message_id=msg.id, score=item["score"], delivered=True
        )
        session.add(rec)
        await session.commit()
        await session.refresh(rec)

        text = f"📌 *Рекомендация* (score: {item['score']:.2f})\n\n{msg.text[:4000]}"
        await message.answer(text, reply_markup=feedback_keyboard(rec.id))


@router.callback_query(F.data.startswith("fb:"))
async def handle_feedback(callback: CallbackQuery, session: AsyncSession):
    _, action, rec_id = callback.data.split(":")
    rec = await session.get(Recommendation, int(rec_id))
    if rec:
        rec.feedback = action
        await session.commit()
    await callback.answer("Спасибо за отзыв!")


# bot/handlers/settings.py
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.models import User

router = Router()


@router.message(Command("interests"))
async def cmd_interests(message: Message, session: AsyncSession):
    text = message.text.replace("/interests", "").strip()
    if not text:
        await message.answer(
            "Опиши свои интересы после команды.\n"
            "Например: /interests ML, криптография, инди-игры, космос"
        )
        return

    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    user.interests = text
    await session.commit()
    await message.answer(f"Интересы обновлены: {text}")


@router.message(Command("schedule"))
async def cmd_schedule(message: Message, session: AsyncSession):
    text = message.text.replace("/schedule", "").strip()
    if not text:
        await message.answer(
            "Укажи расписание в cron-формате.\n"
            "Например: /schedule 0 9 * * * (каждый день в 9:00)\n"
            "Или: /schedule off (отключить)"
        )
        return

    stmt = select(User).where(User.telegram_id == message.from_user.id)
    user = (await session.execute(stmt)).scalar_one_or_none()
    if not user:
        await message.answer("Сначала используй /start")
        return

    user.digest_cron = text if text != "off" else None
    await session.commit()
    if text == "off":
        await message.answer("Автодайджест отключён.")
    else:
        await message.answer(f"Расписание обновлено: {text}")
```

**Step 6: Implement bot/main.py**

```python
# bot/main.py
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession
from core.config import Settings
from core.db import create_engine, create_session_factory
from core.llm import create_llm_provider
from core.embeddings import EmbeddingService
from core.recommender import Recommender
from bot.handlers import start, channels, digest, settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    app_settings = Settings()

    engine = create_engine(app_settings)
    session_factory = create_session_factory(engine)

    llm_provider = create_llm_provider(
        provider=app_settings.LLM_PROVIDER,
        api_key=(
            app_settings.ANTHROPIC_API_KEY
            if app_settings.LLM_PROVIDER == "claude"
            else app_settings.OPENAI_API_KEY
        ),
    )
    embedding_service = EmbeddingService(
        api_key=app_settings.OPENAI_API_KEY,
        model=app_settings.EMBEDDING_MODEL,
        dim=app_settings.EMBEDDING_DIM,
    )
    recommender = Recommender(
        embedding_service=embedding_service,
        llm_provider=llm_provider,
        candidates_limit=app_settings.CANDIDATES_LIMIT,
        digest_size=app_settings.DIGEST_SIZE,
    )

    bot = Bot(token=app_settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    # Middleware to inject session and recommender
    @dp.update.outer_middleware()
    async def db_middleware(handler, event: TelegramObject, data: dict):
        async with session_factory() as session:
            data["session"] = session
            data["recommender"] = recommender
            return await handler(event, data)

    dp.include_router(start.router)
    dp.include_router(channels.router)
    dp.include_router(digest.router)
    dp.include_router(settings.router)

    logger.info("Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
```

**Step 7: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: All tests PASS

**Step 8: Commit**

```bash
git add bot/ tests/test_bot_handlers.py
git commit -m "feat: add aiogram bot with handlers for start, channels, digest, settings"
```

---

### Task 7: Scheduler — Automated digests

**Files:**
- Create: `scheduler/__init__.py`
- Create: `scheduler/jobs.py`
- Test: `tests/test_scheduler.py`

**Step 1: Write the failing test**

```python
# tests/test_scheduler.py
from scheduler.jobs import parse_cron


def test_parse_cron_valid():
    result = parse_cron("0 9 * * *")
    assert result == {"minute": "0", "hour": "9", "day": "*", "month": "*", "day_of_week": "*"}


def test_parse_cron_invalid_returns_none():
    result = parse_cron("invalid")
    assert result is None


def test_parse_cron_none_returns_none():
    result = parse_cron(None)
    assert result is None
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_scheduler.py -v`
Expected: FAIL

**Step 3: Implement scheduler**

```python
# scheduler/__init__.py
# (empty)

# scheduler/jobs.py
import logging
from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from core.models import User, UserChannel, Recommendation, Message
from core.recommender import Recommender
from bot.keyboards import feedback_keyboard

logger = logging.getLogger(__name__)


def parse_cron(cron_str: str | None) -> dict | None:
    if not cron_str:
        return None
    parts = cron_str.strip().split()
    if len(parts) != 5:
        return None
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def send_digest_to_user(
    bot: Bot,
    session_factory: async_sessionmaker,
    recommender: Recommender,
    user_id: int,
    telegram_id: int,
    interests: str,
):
    async with session_factory() as session:
        ch_stmt = select(UserChannel.channel_id).where(UserChannel.user_id == user_id)
        channel_ids = (await session.execute(ch_stmt)).scalars().all()
        if not channel_ids:
            return

        ranked = await recommender.recommend(
            session=session,
            user_id=user_id,
            interests=interests,
            channel_ids=list(channel_ids),
        )

        if not ranked:
            return

        await bot.send_message(telegram_id, "📬 Твой дайджест готов!")

        for item in ranked:
            msg = await session.get(Message, item["message_id"])
            if not msg:
                continue

            rec = Recommendation(
                user_id=user_id, message_id=msg.id, score=item["score"], delivered=True
            )
            session.add(rec)
            await session.commit()
            await session.refresh(rec)

            text = f"📌 *Рекомендация* (score: {item['score']:.2f})\n\n{msg.text[:4000]}"
            await bot.send_message(telegram_id, text, reply_markup=feedback_keyboard(rec.id))
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_scheduler.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scheduler/ tests/test_scheduler.py
git commit -m "feat: add scheduler for automated digests"
```

---

### Task 8: Integration — Wire scheduler into bot, final docker test

**Files:**
- Modify: `bot/main.py` (add APScheduler startup)
- Modify: `alembic/env.py` (finalize async config)

**Step 1: Add scheduler to bot/main.py**

Add after `dp.include_router(settings.router)`:

```python
    # Scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    from scheduler.jobs import send_digest_to_user, parse_cron

    scheduler = AsyncIOScheduler()

    async def schedule_digests():
        async with session_factory() as session:
            stmt = select(User).where(User.digest_cron.isnot(None))
            users = (await session.execute(stmt)).scalars().all()
            for user in users:
                cron = parse_cron(user.digest_cron)
                if not cron:
                    continue
                job_id = f"digest_{user.id}"
                scheduler.add_job(
                    send_digest_to_user,
                    CronTrigger(**cron),
                    id=job_id,
                    replace_existing=True,
                    kwargs={
                        "bot": bot,
                        "session_factory": session_factory,
                        "recommender": recommender,
                        "user_id": user.id,
                        "telegram_id": user.telegram_id,
                        "interests": user.interests or "",
                    },
                )

    await schedule_digests()
    scheduler.start()
    logger.info("Scheduler started.")
```

Import `User` and `select` at top of `bot/main.py`:
```python
from sqlalchemy import select
from core.models import User
```

**Step 2: Full docker-compose test**

```bash
cp .env.example .env
# Edit .env with real credentials
docker compose up --build -d
docker compose logs -f
```

**Step 3: Run full test suite**

Run: `venv/bin/pytest tests/ -v --tb=short`
Expected: All tests PASS

**Step 4: Commit**

```bash
git add bot/main.py
git commit -m "feat: integrate APScheduler into bot for automated digests"
```

---

### Task 9: Final polish — .env.example, pytest config

**Files:**
- Create: `pyproject.toml` (pytest config section)
- Verify: all `__init__.py` files exist

**Step 1: Create pyproject.toml**

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Step 2: Run full test suite one more time**

Run: `venv/bin/pytest tests/ -v`
Expected: All PASS

**Step 3: Final commit**

```bash
git add pyproject.toml
git commit -m "chore: add pytest config"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Infrastructure | config, docker, requirements |
| 2 | Database | models, alembic, migrations |
| 3 | LLM Abstraction | base, openai, claude, embeddings |
| 4 | Recommender | two-stage pipeline |
| 5 | Collector | Telethon userbot |
| 6 | Bot | aiogram handlers |
| 7 | Scheduler | APScheduler jobs |
| 8 | Integration | wire scheduler, docker test |
| 9 | Polish | pytest config, final verification |
