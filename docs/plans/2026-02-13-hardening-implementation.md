# Tematch Hardening — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deduplication, digest windowing, LLM cost protection, and collector resync to make Tematch production-ready.

**Architecture:** Four hardening features layered onto the existing two-process (collector + bot) design. New columns on User/Message, new LLMUsage table, new EmbeddingBuffer and resync modules. All changes are additive — no existing behavior is removed, only extended.

**Tech Stack:** Python 3.9+, SQLAlchemy 2 async, Alembic, pgvector, Telethon, aiogram 3

**Design doc:** `docs/plans/2026-02-13-hardening-design.md`

---

### Task 1: Models, Config, Migration — Foundation

**Files:**
- Modify: `core/models.py`
- Modify: `core/config.py`
- Create: `alembic/versions/xxx_hardening.py`
- Modify: `tests/test_models.py`
- Create: `tests/test_config_hardening.py`

**Step 1: Write the failing test for new model fields**

```python
# tests/test_config_hardening.py
from core.config import Settings


def test_hardening_settings_defaults():
    settings = Settings(
        TG_API_ID=123,
        TG_API_HASH="abc",
        TG_BOT_TOKEN="token",
        DATABASE_URL="postgresql+asyncpg://localhost/test",
    )
    assert settings.DIGEST_WINDOW_MAX_HOURS == 72
    assert settings.MAX_DIGESTS_PER_DAY == 3
    assert settings.DAILY_TOKEN_BUDGET == 500_000
    assert settings.EMBEDDING_BATCH_SIZE == 20
    assert settings.EMBEDDING_FLUSH_INTERVAL == 30
    assert settings.RESYNC_MAX_HOURS == 72
    assert settings.RESYNC_BATCH_SIZE == 100
```

Add to `tests/test_models.py`:

```python
from core.models import LLMUsage


def test_message_has_content_hash():
    m = Message(channel_id=1, telegram_msg_id=100, text="Hello world", content_hash="abc123")
    assert m.content_hash == "abc123"


def test_user_has_last_digest_at():
    u = User(telegram_id=123)
    assert u.last_digest_at is None


def test_user_has_interests_embedding():
    u = User(telegram_id=123)
    assert u.interests_embedding is None


def test_llm_usage_model():
    from datetime import date
    usage = LLMUsage(
        date=date.today(),
        provider="openai",
        operation="rank_messages",
        tokens_in=500,
        tokens_out=100,
        cost_estimate=0.001,
    )
    assert usage.provider == "openai"
    assert usage.tokens_in == 500
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/pytest tests/test_config_hardening.py tests/test_models.py -v`
Expected: FAIL (missing attributes/imports)

**Step 3: Add new settings to config**

In `core/config.py`, add after `DEFAULT_DIGEST_CRON`:

```python
    # Hardening
    DIGEST_WINDOW_MAX_HOURS: int = 72
    MAX_DIGESTS_PER_DAY: int = 3
    DAILY_TOKEN_BUDGET: int = 500_000
    EMBEDDING_BATCH_SIZE: int = 20
    EMBEDDING_FLUSH_INTERVAL: int = 30
    RESYNC_MAX_HOURS: int = 72
    RESYNC_BATCH_SIZE: int = 100
```

**Step 4: Add new fields to models**

In `core/models.py`:

Add to `User` class (after `created_at`):
```python
    last_digest_at: Mapped[Optional[datetime]] = mapped_column()
    interests_embedding = mapped_column(Vector(1536), nullable=True)
```

Add to `Message` class (after `text`):
```python
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True)
```

Add new `LLMUsage` class at the bottom:
```python
import datetime as dt  # add at top alongside existing datetime import

class LLMUsage(Base):
    __tablename__ = "llm_usage"

    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[dt.date] = mapped_column(index=True, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    operation: Mapped[str] = mapped_column(String(50), nullable=False)
    tokens_in: Mapped[int] = mapped_column(nullable=False)
    tokens_out: Mapped[int] = mapped_column(nullable=False)
    cost_estimate: Mapped[float] = mapped_column(Float, default=0.0)
```

**Step 5: Run tests to verify they pass**

Run: `venv/bin/pytest tests/test_config_hardening.py tests/test_models.py -v`
Expected: PASS

**Step 6: Create Alembic migration**

Run: `venv/bin/alembic revision -m "hardening columns and llm_usage table"`

Then fill in the migration with:
- `ALTER TABLE users ADD COLUMN last_digest_at TIMESTAMP`
- `ALTER TABLE users ADD COLUMN interests_embedding vector(1536)`
- `ALTER TABLE messages ADD COLUMN content_hash VARCHAR(64)`
- `CREATE INDEX ix_messages_content_hash ON messages(content_hash)`
- `CREATE TABLE llm_usage(...)`
- Backfill `content_hash` for existing messages

**Step 7: Apply migration**

Run: `venv/bin/alembic upgrade head`

**Step 8: Lint and commit**

Run: `venv/bin/ruff check core/models.py core/config.py tests/ alembic/versions/ --fix`

```bash
git add core/models.py core/config.py alembic/versions/ tests/test_models.py tests/test_config_hardening.py
git commit -m "feat: add hardening models — content_hash, last_digest_at, interests_embedding, LLMUsage"
```

---

### Task 2: Content Hash + Dedup Filter

**Files:**
- Create: `core/content_hash.py`
- Modify: `collector/handlers.py`
- Modify: `core/recommender.py`
- Create: `tests/test_dedup.py`

**Step 1: Write the failing test for content hash**

```python
# tests/test_dedup.py
from core.content_hash import compute_content_hash


def test_compute_content_hash_basic():
    h = compute_content_hash("Hello World")
    assert len(h) == 64  # SHA-256 hex


def test_compute_content_hash_normalizes_whitespace():
    h1 = compute_content_hash("hello   world")
    h2 = compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_case_insensitive():
    h1 = compute_content_hash("Hello World")
    h2 = compute_content_hash("hello world")
    assert h1 == h2


def test_compute_content_hash_strips():
    h1 = compute_content_hash("  hello world  ")
    h2 = compute_content_hash("hello world")
    assert h1 == h2
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_dedup.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.content_hash'`

**Step 3: Implement content_hash module**

```python
# core/content_hash.py
import hashlib
import re


def compute_content_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_dedup.py -v`
Expected: PASS (4 tests)

**Step 5: Write failing test for dedup in recommender**

Add to `tests/test_dedup.py`:

```python
from core.recommender import deduplicate_candidates


def test_deduplicate_keeps_earliest():
    from unittest.mock import MagicMock
    from datetime import datetime

    msg1 = MagicMock(id=1, text="Hello", content_hash="aaa", date=datetime(2026, 1, 1, 10, 0))
    msg2 = MagicMock(id=2, text="Hello", content_hash="aaa", date=datetime(2026, 1, 1, 12, 0))
    msg3 = MagicMock(id=3, text="Other", content_hash="bbb", date=datetime(2026, 1, 1, 11, 0))

    result = deduplicate_candidates([msg1, msg2, msg3])
    assert len(result) == 2
    ids = [m.id for m in result]
    assert 1 in ids  # earliest of hash "aaa"
    assert 3 in ids
    assert 2 not in ids
```

**Step 6: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_dedup.py::test_deduplicate_keeps_earliest -v`
Expected: FAIL with `ImportError`

**Step 7: Implement deduplicate_candidates in recommender**

Add to `core/recommender.py` (as a module-level function):

```python
def deduplicate_candidates(candidates: list) -> list:
    seen: dict[str, object] = {}
    for msg in candidates:
        h = msg.content_hash
        if h is None:
            seen[f"_nohash_{msg.id}"] = msg
        elif h not in seen or msg.date < seen[h].date:
            seen[h] = msg
    return list(seen.values())
```

Update `Recommender.recommend()` to call it after pgvector query:

```python
        candidates = result.scalars().all()
        candidates = deduplicate_candidates(candidates)
```

**Step 8: Modify collector/handlers.py to compute content_hash**

In `collector/handlers.py`, import `compute_content_hash` and add the hash when creating Message:

```python
from core.content_hash import compute_content_hash

# Inside handle_new_message, before creating Message:
    content_hash = compute_content_hash(text)

    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        date=date,
        embedding=embedding,
        content_hash=content_hash,
    )
```

**Step 9: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 10: Lint and commit**

Run: `venv/bin/ruff check core/content_hash.py core/recommender.py collector/handlers.py tests/test_dedup.py --fix`

```bash
git add core/content_hash.py core/recommender.py collector/handlers.py tests/test_dedup.py
git commit -m "feat: add content-hash dedup — compute on ingest, filter in recommender"
```

---

### Task 3: Digest Window

**Files:**
- Modify: `core/recommender.py`
- Modify: `bot/handlers/digest.py`
- Create: `tests/test_digest_window.py`

**Step 1: Write the failing test for window_start calculation**

```python
# tests/test_digest_window.py
from datetime import datetime, timedelta
from core.recommender import compute_window_start


def test_window_start_first_time_user():
    now = datetime(2026, 2, 13, 12, 0, 0)
    start = compute_window_start(last_digest_at=None, max_hours=72, now=now)
    assert start == now - timedelta(hours=24)


def test_window_start_recent_digest():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 13, 3, 0, 0)  # 9 hours ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == last


def test_window_start_old_digest_capped_at_max():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 1, 12, 0, 0)  # 12 days ago
    start = compute_window_start(last_digest_at=last, max_hours=72, now=now)
    assert start == now - timedelta(hours=72)
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_digest_window.py -v`
Expected: FAIL with `ImportError`

**Step 3: Implement compute_window_start**

Add to `core/recommender.py`:

```python
from datetime import datetime, timedelta


def compute_window_start(
    last_digest_at: datetime | None,
    max_hours: int,
    now: datetime | None = None,
) -> datetime:
    if now is None:
        now = datetime.utcnow()
    if last_digest_at is None:
        return now - timedelta(hours=24)
    return max(last_digest_at, now - timedelta(hours=max_hours))
```

Note: since this is a standalone function (not inside `Mapped[]`), the `datetime | None` syntax is fine on Python 3.9 because it's under `from __future__ import annotations`. But `recommender.py` does NOT have `from __future__ import annotations`, so use `Optional[datetime]` instead:

```python
from typing import Optional

def compute_window_start(
    last_digest_at: Optional[datetime],
    max_hours: int,
    now: Optional[datetime] = None,
) -> datetime:
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_digest_window.py -v`
Expected: PASS (3 tests)

**Step 5: Add window_start to Recommender.recommend()**

Update `Recommender.recommend()` signature to accept `window_start`:

```python
    async def recommend(
        self,
        session: AsyncSession,
        user_id: int,
        interests: str,
        channel_ids: list[int],
        window_start: Optional[datetime] = None,
    ) -> list[dict]:
```

Add filter to pgvector query:

```python
        stmt = (
            select(Message)
            .where(Message.channel_id.in_(channel_ids))
            .where(Message.embedding.isnot(None))
        )
        if window_start:
            stmt = stmt.where(Message.date >= window_start)
        stmt = stmt.order_by(
            Message.embedding.cosine_distance(query_vector)
        ).limit(self.candidates_limit)
```

**Step 6: Update bot/handlers/digest.py to pass window_start and update last_digest_at**

In `cmd_digest`, after fetching user, compute window and pass to recommender:

```python
    from core.recommender import compute_window_start

    window = compute_window_start(
        last_digest_at=user.last_digest_at,
        max_hours=72,  # later: get from settings
    )

    ranked = await recommender.recommend(
        session=session,
        user_id=user.id,
        interests=user.interests,
        channel_ids=list(channel_ids),
        window_start=window,
    )
```

After sending all recommendations, update `last_digest_at`:

```python
    user.last_digest_at = datetime.utcnow()
    await session.commit()
```

**Step 7: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 8: Lint and commit**

Run: `venv/bin/ruff check core/recommender.py bot/handlers/digest.py tests/test_digest_window.py --fix`

```bash
git add core/recommender.py bot/handlers/digest.py tests/test_digest_window.py
git commit -m "feat: add hybrid digest window — since-last + max 72h"
```

---

### Task 4: LLM Usage Tracking

**Files:**
- Create: `core/llm_usage.py`
- Modify: `core/llm/openai_provider.py`
- Modify: `core/llm/claude_provider.py`
- Modify: `core/embeddings.py`
- Create: `tests/test_llm_usage.py`

**Step 1: Write the failing test for usage logger**

```python
# tests/test_llm_usage.py
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm_usage import log_usage, get_daily_token_total


@pytest.mark.asyncio
async def test_log_usage():
    mock_session = AsyncMock()
    await log_usage(
        session=mock_session,
        provider="openai",
        operation="rank_messages",
        tokens_in=500,
        tokens_out=100,
    )
    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_daily_token_total():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 42000
    mock_session.execute.return_value = mock_result

    total = await get_daily_token_total(mock_session)
    assert total == 42000


@pytest.mark.asyncio
async def test_get_daily_token_total_none_returns_zero():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    total = await get_daily_token_total(mock_session)
    assert total == 0
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_llm_usage.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement core/llm_usage.py**

```python
# core/llm_usage.py
import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import LLMUsage


async def log_usage(
    session: AsyncSession,
    provider: str,
    operation: str,
    tokens_in: int,
    tokens_out: int,
    cost_estimate: float = 0.0,
) -> None:
    entry = LLMUsage(
        date=dt.date.today(),
        provider=provider,
        operation=operation,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        cost_estimate=cost_estimate,
    )
    session.add(entry)
    await session.commit()


async def get_daily_token_total(session: AsyncSession) -> int:
    stmt = select(func.sum(LLMUsage.tokens_in + LLMUsage.tokens_out)).where(
        LLMUsage.date == dt.date.today()
    )
    result = await session.execute(stmt)
    total = result.scalar_one_or_none()
    return total or 0
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_llm_usage.py -v`
Expected: PASS (3 tests)

**Step 5: Update LLM providers to return usage metadata**

Modify `core/llm/base.py` — change `rank_messages` return type to include usage:

```python
from dataclasses import dataclass


@dataclass
class LLMResult:
    ranked: list[dict]
    tokens_in: int
    tokens_out: int


class LLMProvider(ABC):
    @abstractmethod
    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        ...
```

Update `core/llm/openai_provider.py`:

```python
    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        ...
        response = await self.client.chat.completions.create(...)
        usage = response.usage
        return LLMResult(
            ranked=json.loads(response.choices[0].message.content),
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
```

Update `core/llm/claude_provider.py`:

```python
    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        ...
        response = await self.client.messages.create(...)
        return LLMResult(
            ranked=json.loads(response.content[0].text),
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
```

**Step 6: Update EmbeddingService to return usage**

Modify `core/embeddings.py`:

```python
@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    tokens: int


class EmbeddingService:
    async def embed_text(self, text: str) -> EmbeddingResult:
        response = await self.client.embeddings.create(...)
        return EmbeddingResult(
            embeddings=[response.data[0].embedding],
            tokens=response.usage.total_tokens if response.usage else 0,
        )

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        response = await self.client.embeddings.create(...)
        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            tokens=response.usage.total_tokens if response.usage else 0,
        )
```

**Step 7: Update all callers of embed_text/embed_texts to use .embeddings[0] etc.**

Callers:
- `collector/handlers.py`: `embedding = (await embedding_service.embed_text(text)).embeddings[0]`
- `core/recommender.py`: `query_vector = (await self.embedding_service.embed_text(interests)).embeddings[0]`

Update callers of `rank_messages` to use `.ranked`:
- `core/recommender.py`: `llm_result = await self.llm_provider.rank_messages(...)` then `ranked = llm_result.ranked`

**Step 8: Update existing tests to match new return types**

Update `tests/test_llm.py` — factory tests don't call `rank_messages`, so they still pass.

Update `tests/test_embeddings.py`:

```python
async def test_embed_text_returns_result():
    ...
    result = await service.embed_text("hello world")
    assert len(result.embeddings[0]) == 1536
    assert result.tokens == 0  # mock doesn't have usage
```

Update `tests/test_recommender.py`:
- mock_embedding returns `EmbeddingResult`
- mock_llm returns `LLMResult`

**Step 9: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 10: Lint and commit**

```bash
git add core/llm_usage.py core/llm/ core/embeddings.py core/recommender.py collector/handlers.py tests/
git commit -m "feat: add LLM usage tracking — log tokens per call, return usage metadata"
```

---

### Task 5: Rate Limiting — Digest Limit + Token Budget

**Files:**
- Modify: `bot/handlers/digest.py`
- Create: `tests/test_llm_limits.py`

**Step 1: Write the failing test for digest rate limit**

```python
# tests/test_llm_limits.py
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.handlers.digest import count_digests_today


@pytest.mark.asyncio
async def test_count_digests_today_empty():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = 0
    mock_session.execute.return_value = mock_result

    count = await count_digests_today(mock_session, user_id=1)
    assert count == 0
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_llm_limits.py -v`
Expected: FAIL with `ImportError`

**Step 3: Implement count_digests_today in digest handler**

Add to `bot/handlers/digest.py`:

```python
from datetime import datetime, timedelta
from sqlalchemy import func


async def count_digests_today(session: AsyncSession, user_id: int) -> int:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    stmt = select(func.count(func.distinct(
        func.date_trunc("minute", Recommendation.created_at)
    ))).where(
        Recommendation.user_id == user_id,
        Recommendation.delivered.is_(True),
        Recommendation.created_at >= today_start,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none() or 0
```

**Step 4: Add rate limit check to cmd_digest**

In `cmd_digest`, after the user checks and before calling recommender:

```python
    digest_count = await count_digests_today(session, user.id)
    if digest_count >= 3:  # later: from settings
        await message.answer(
            f"Лимит дайджестов на сегодня: {digest_count}/3. Попробуй завтра."
        )
        return
```

**Step 5: Add token budget check**

In `cmd_digest`, before calling recommender:

```python
    from core.llm_usage import get_daily_token_total

    daily_tokens = await get_daily_token_total(session)
    if daily_tokens >= 500_000:  # later: from settings
        await message.answer("Дневной лимит токенов исчерпан. Попробуй завтра.")
        return
```

**Step 6: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 7: Lint and commit**

```bash
git add bot/handlers/digest.py tests/test_llm_limits.py
git commit -m "feat: add rate limiting — per-user digest cap + global token budget"
```

---

### Task 6: Embedding Batching in Collector

**Files:**
- Create: `collector/embedding_buffer.py`
- Modify: `collector/handlers.py`
- Modify: `collector/main.py`
- Create: `tests/test_embedding_buffer.py`

**Step 1: Write the failing test for EmbeddingBuffer**

```python
# tests/test_embedding_buffer.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.embedding_buffer import EmbeddingBuffer


@pytest.mark.asyncio
async def test_buffer_accumulates_and_flushes():
    mock_session_factory = AsyncMock()
    mock_session = AsyncMock()
    mock_session_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_factory.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_embedding = AsyncMock()
    from core.embeddings import EmbeddingResult
    mock_embedding.embed_texts.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536, [0.2] * 1536],
        tokens=100,
    )

    buffer = EmbeddingBuffer(
        embedding_service=mock_embedding,
        session_factory=mock_session_factory,
        batch_size=2,
    )
    buffer.add(message_id=1, text="hello world message one")
    assert len(buffer._pending) == 1

    buffer.add(message_id=2, text="hello world message two")
    # Should auto-flush at batch_size=2
    await buffer.flush()
    mock_embedding.embed_texts.assert_called_once()


def test_buffer_add_does_not_flush_below_threshold():
    buffer = EmbeddingBuffer(
        embedding_service=MagicMock(),
        session_factory=MagicMock(),
        batch_size=10,
    )
    buffer.add(message_id=1, text="hello")
    assert len(buffer._pending) == 1
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_embedding_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement EmbeddingBuffer**

```python
# collector/embedding_buffer.py
import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.embeddings import EmbeddingService
from core.models import Message

logger = logging.getLogger(__name__)


class EmbeddingBuffer:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        session_factory: async_sessionmaker,
        batch_size: int = 20,
    ):
        self.embedding_service = embedding_service
        self.session_factory = session_factory
        self.batch_size = batch_size
        self._pending: list[tuple[int, str]] = []

    def add(self, message_id: int, text: str) -> None:
        self._pending.append((message_id, text))

    @property
    def should_flush(self) -> bool:
        return len(self._pending) >= self.batch_size

    async def flush(self) -> None:
        if not self._pending:
            return

        batch = self._pending[:]
        self._pending.clear()

        msg_ids = [b[0] for b in batch]
        texts = [b[1] for b in batch]

        try:
            result = await self.embedding_service.embed_texts(texts)
            embeddings = result.embeddings
        except Exception:
            logger.exception("Batch embedding failed for %d messages", len(batch))
            return

        async with self.session_factory() as session:
            for msg_id, embedding in zip(msg_ids, embeddings):
                stmt = (
                    update(Message)
                    .where(Message.id == msg_id)
                    .values(embedding=embedding)
                )
                await session.execute(stmt)
            await session.commit()

        logger.info("Flushed %d embeddings", len(batch))
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_embedding_buffer.py -v`
Expected: PASS

**Step 5: Update collector/handlers.py — store without embedding, add to buffer**

Remove embedding generation from `handle_new_message`. Store message with `embedding=None`, then add to buffer:

```python
async def handle_new_message(
    session: AsyncSession,
    channel_telegram_id: int,
    message_id: int,
    text: str,
    date: datetime,
    embedding_buffer: "EmbeddingBuffer",
):
    ...
    # Remove embedding generation, just store the message
    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        date=date,
        content_hash=content_hash,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    # Add to embedding buffer
    embedding_buffer.add(message_id=msg.id, text=text)

    channel.last_fetched_at = datetime.utcnow()
    await session.commit()
```

**Step 6: Update collector/main.py — create buffer, periodic flush**

```python
import asyncio
from collector.embedding_buffer import EmbeddingBuffer

async def main():
    ...
    embedding_buffer = EmbeddingBuffer(
        embedding_service=embedding_service,
        session_factory=session_factory,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
    )

    @client.on(events.NewMessage)
    async def on_new_message(event):
        ...
        await handle_new_message(
            session=session,
            channel_telegram_id=chat.id,
            message_id=event.id,
            text=event.raw_text,
            date=event.date,
            embedding_buffer=embedding_buffer,
        )
        if embedding_buffer.should_flush:
            await embedding_buffer.flush()

    # Periodic flush task
    async def periodic_flush():
        while True:
            await asyncio.sleep(settings.EMBEDDING_FLUSH_INTERVAL)
            await embedding_buffer.flush()

    await client.start()
    asyncio.create_task(periodic_flush())
    ...
```

**Step 7: Update existing collector test**

Update `tests/test_collector.py` — `test_get_active_channel_ids` doesn't touch handler, so it's unaffected.

**Step 8: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 9: Lint and commit**

```bash
git add collector/ tests/test_embedding_buffer.py tests/test_collector.py
git commit -m "feat: add embedding batching — buffer in collector, periodic flush"
```

---

### Task 7: Interests Embedding Cache

**Files:**
- Modify: `bot/handlers/settings.py`
- Modify: `core/recommender.py`
- Create: `tests/test_interests_cache.py`

**Step 1: Write the failing test**

```python
# tests/test_interests_cache.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from core.recommender import Recommender


@pytest.mark.asyncio
async def test_recommend_uses_cached_interests_embedding():
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_llm = AsyncMock()

    from core.llm.base import LLMResult
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[{"message_id": 1, "score": 0.9}],
        tokens_in=100,
        tokens_out=50,
    )

    mock_result = MagicMock()
    mock_msg = MagicMock(id=1, text="ML news", content_hash="aaa", date=None)
    mock_result.scalars.return_value.all.return_value = [mock_msg]
    mock_session.execute.return_value = mock_result

    recommender = Recommender(
        embedding_service=mock_embedding,
        llm_provider=mock_llm,
    )

    # Pass cached vector — should NOT call embedding service
    cached_vector = [0.1] * 1536
    await recommender.recommend(
        session=mock_session,
        user_id=1,
        interests="ML",
        channel_ids=[1],
        interests_embedding=cached_vector,
    )

    mock_embedding.embed_text.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_interests_cache.py -v`
Expected: FAIL

**Step 3: Update Recommender.recommend() to accept optional cached embedding**

```python
    async def recommend(
        self,
        session: AsyncSession,
        user_id: int,
        interests: str,
        channel_ids: list[int],
        window_start: Optional[datetime] = None,
        interests_embedding: Optional[list[float]] = None,
    ) -> list[dict]:
        if interests_embedding:
            query_vector = interests_embedding
        else:
            embed_result = await self.embedding_service.embed_text(interests)
            query_vector = embed_result.embeddings[0]
```

**Step 4: Update bot/handlers/settings.py — recompute embedding on /interests**

```python
async def cmd_interests(message: Message, session: AsyncSession, embedding_service: EmbeddingService):
    ...
    user.interests = text
    result = await embedding_service.embed_text(text)
    user.interests_embedding = result.embeddings[0]
    await session.commit()
    await message.answer(f"Интересы обновлены: {text}")
```

Note: `embedding_service` is already injected via middleware in `bot/main.py`. Add it to the middleware `data` dict.

**Step 5: Update bot/handlers/digest.py — pass cached embedding to recommender**

```python
    ranked = await recommender.recommend(
        session=session,
        user_id=user.id,
        interests=user.interests,
        channel_ids=list(channel_ids),
        window_start=window,
        interests_embedding=user.interests_embedding,
    )
```

**Step 6: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 7: Lint and commit**

```bash
git add core/recommender.py bot/handlers/settings.py bot/handlers/digest.py bot/main.py tests/test_interests_cache.py
git commit -m "feat: cache interests embedding — recompute on /interests, skip API in recommender"
```

---

### Task 8: Collector Resync on Startup

**Files:**
- Create: `collector/resync.py`
- Modify: `collector/main.py`
- Create: `tests/test_resync.py`

**Step 1: Write the failing test**

```python
# tests/test_resync.py
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.resync import compute_resync_offset


def test_resync_offset_from_last_fetched():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 2, 13, 6, 0, 0)
    offset = compute_resync_offset(last_fetched_at=last, max_hours=72, now=now)
    assert offset == last


def test_resync_offset_none_uses_max():
    now = datetime(2026, 2, 13, 12, 0, 0)
    offset = compute_resync_offset(last_fetched_at=None, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)


def test_resync_offset_capped():
    now = datetime(2026, 2, 13, 12, 0, 0)
    last = datetime(2026, 1, 1, 0, 0, 0)  # very old
    offset = compute_resync_offset(last_fetched_at=last, max_hours=72, now=now)
    assert offset == now - timedelta(hours=72)
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/pytest tests/test_resync.py -v`
Expected: FAIL with `ModuleNotFoundError`

**Step 3: Implement collector/resync.py**

```python
# collector/resync.py
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker
from telethon import TelegramClient

from collector.channel_manager import get_active_channel_ids
from collector.handlers import handle_new_message
from core.models import Channel

logger = logging.getLogger(__name__)


def compute_resync_offset(
    last_fetched_at: Optional[datetime],
    max_hours: int,
    now: Optional[datetime] = None,
) -> datetime:
    if now is None:
        now = datetime.utcnow()
    floor = now - timedelta(hours=max_hours)
    if last_fetched_at is None:
        return floor
    return max(last_fetched_at, floor)


async def resync_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker,
    embedding_buffer,
    max_hours: int = 72,
    batch_size: int = 100,
) -> None:
    async with session_factory() as session:
        active_tg_ids = await get_active_channel_ids(session)
        stmt = select(Channel).where(Channel.telegram_id.in_(active_tg_ids))
        channels = (await session.execute(stmt)).scalars().all()

    for channel in channels:
        offset_date = compute_resync_offset(channel.last_fetched_at, max_hours)
        logger.info(
            "Resync channel %s (id=%d) from %s",
            channel.title or channel.username,
            channel.telegram_id,
            offset_date,
        )

        count = 0
        async for msg in client.iter_messages(
            channel.telegram_id,
            offset_date=offset_date,
            limit=batch_size,
        ):
            if not msg.text or len(msg.text.strip()) < 20:
                continue

            async with session_factory() as session:
                await handle_new_message(
                    session=session,
                    channel_telegram_id=channel.telegram_id,
                    message_id=msg.id,
                    text=msg.text,
                    date=msg.date,
                    embedding_buffer=embedding_buffer,
                )
            count += 1

        logger.info("Resync channel %s: %d messages processed", channel.title, count)

        # Flush embeddings after each channel
        await embedding_buffer.flush()

        # Small delay to avoid Telegram rate limits
        await asyncio.sleep(1)
```

**Step 4: Run test to verify it passes**

Run: `venv/bin/pytest tests/test_resync.py -v`
Expected: PASS (3 tests)

**Step 5: Wire resync into collector/main.py**

In `collector/main.py`, call `resync_channels` after `client.start()` but before `run_until_disconnected`:

```python
    from collector.resync import resync_channels

    await client.start()

    # Catch up on missed messages
    logger.info("Starting resync...")
    await resync_channels(
        client=client,
        session_factory=session_factory,
        embedding_buffer=embedding_buffer,
        max_hours=settings.RESYNC_MAX_HOURS,
        batch_size=settings.RESYNC_BATCH_SIZE,
    )
    logger.info("Resync complete. Listening for live messages...")

    asyncio.create_task(periodic_flush())
    await client.run_until_disconnected()
```

**Step 6: Run all tests**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 7: Lint and commit**

```bash
git add collector/resync.py collector/main.py tests/test_resync.py
git commit -m "feat: add collector resync — catch up missed messages on startup"
```

---

### Task 9: Update .env.example + Final Verification

**Files:**
- Modify: `.env.example`

**Step 1: Add new settings to .env.example**

```
# Hardening
DIGEST_WINDOW_MAX_HOURS=72
MAX_DIGESTS_PER_DAY=3
DAILY_TOKEN_BUDGET=500000
EMBEDDING_BATCH_SIZE=20
EMBEDDING_FLUSH_INTERVAL=30
RESYNC_MAX_HOURS=72
RESYNC_BATCH_SIZE=100
```

**Step 2: Run full test suite**

Run: `venv/bin/pytest tests/ -v`
Expected: ALL PASS

**Step 3: Run full lint**

Run: `venv/bin/ruff check . --fix`

**Step 4: Commit**

```bash
git add .env.example
git commit -m "chore: add hardening settings to .env.example"
```

---

## Summary

| Task | What | Key Files |
|------|------|-----------|
| 1 | Models + config + migration | `core/models.py`, `core/config.py`, migration |
| 2 | Content hash + dedup filter | `core/content_hash.py`, `core/recommender.py` |
| 3 | Digest window (since-last + 72h cap) | `core/recommender.py`, `bot/handlers/digest.py` |
| 4 | LLM usage tracking | `core/llm_usage.py`, providers, `core/embeddings.py` |
| 5 | Rate limiting (digest cap + token budget) | `bot/handlers/digest.py` |
| 6 | Embedding batching | `collector/embedding_buffer.py` |
| 7 | Interests embedding cache | `bot/handlers/settings.py`, `core/recommender.py` |
| 8 | Collector resync on startup | `collector/resync.py`, `collector/main.py` |
| 9 | .env.example + final verification | `.env.example` |
