# Channel Diversity — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure the digest includes messages from multiple channels by building a diverse candidate pool and filtering by quality.

**Architecture:** Replace single pgvector query with per-channel queries (fair slot allocation), increase `digest_size` to 30, add quality threshold (score >= 0.5) to drop non-relevant items after LLM ranking.

**Tech Stack:** Python 3.9, SQLAlchemy 2 async, pgvector

---

### Task 1: Write failing tests for diverse pool and quality gate

**Files:**
- Modify: `tests/test_recommender.py`

**Step 1: Write failing tests**

Add to the END of `tests/test_recommender.py`:

```python
from math import ceil

from core.recommender import Recommender, deduplicate_candidates


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_recommend_diverse_pool_queries_each_channel(_mock_log):
    """Recommender should query each channel separately for fair representation."""
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_embedding.embed_text.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536], tokens=10
    )
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[
            {"message_id": 1, "score": 0.95},
            {"message_id": 4, "score": 0.80},
        ],
        tokens_in=500,
        tokens_out=100,
    )

    # Mock DB: two execute calls (one per channel)
    msg_ch1_a = MagicMock(id=1, text="Ch1 msg A", channel_id=1, content_hash="h1", date=None)
    msg_ch1_b = MagicMock(id=2, text="Ch1 msg B", channel_id=1, content_hash="h2", date=None)
    msg_ch2_a = MagicMock(id=3, text="Ch2 msg A", channel_id=2, content_hash="h3", date=None)
    msg_ch2_b = MagicMock(id=4, text="Ch2 msg B", channel_id=2, content_hash="h4", date=None)

    result1 = MagicMock()
    result1.scalars.return_value.all.return_value = [msg_ch1_a, msg_ch1_b]
    result2 = MagicMock()
    result2.scalars.return_value.all.return_value = [msg_ch2_a, msg_ch2_b]
    mock_session.execute.side_effect = [result1, result2]

    recommender = Recommender(
        embedding_service=mock_embedding,
        llm_provider=mock_llm,
        candidates_limit=50,
        digest_size=30,
    )

    results = await recommender.recommend(
        session=mock_session,
        user_id=1,
        interests="news",
        channel_ids=[1, 2],
    )

    # Should have called execute twice (one per channel)
    assert mock_session.execute.call_count == 2
    # LLM should receive messages from both channels
    llm_call_args = mock_llm.rank_messages.call_args
    msg_ids = {m["id"] for m in llm_call_args.kwargs["messages"]}
    assert 1 in msg_ids  # from channel 1
    assert 3 in msg_ids or 4 in msg_ids  # from channel 2


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_recommend_quality_gate_filters_low_scores(_mock_log):
    """Messages with score < 0.5 should be filtered out."""
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_embedding.embed_text.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536], tokens=10
    )
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[
            {"message_id": 1, "score": 0.95},
            {"message_id": 2, "score": 0.80},
            {"message_id": 3, "score": 0.30},  # below threshold
            {"message_id": 4, "score": 0.10},  # below threshold
        ],
        tokens_in=500,
        tokens_out=100,
    )

    msg1 = MagicMock(id=1, text="Relevant", channel_id=1, content_hash="h1", date=None)
    result1 = MagicMock()
    result1.scalars.return_value.all.return_value = [msg1]
    mock_session.execute.return_value = result1

    recommender = Recommender(
        embedding_service=mock_embedding,
        llm_provider=mock_llm,
        candidates_limit=50,
        digest_size=30,
        quality_threshold=0.5,
    )

    results = await recommender.recommend(
        session=mock_session,
        user_id=1,
        interests="news",
        channel_ids=[1],
    )

    # Only 2 messages should pass the quality gate
    assert len(results) == 2
    assert all(r["score"] >= 0.5 for r in results)


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_recommend_per_channel_limit(_mock_log):
    """Each channel should get ceil(candidates_limit / num_channels) slots."""
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_embedding.embed_text.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536], tokens=10
    )
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[], tokens_in=100, tokens_out=50,
    )

    # 3 channels, candidates_limit=50 => ceil(50/3) = 17 per channel
    result_empty = MagicMock()
    result_empty.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = result_empty

    recommender = Recommender(
        embedding_service=mock_embedding,
        llm_provider=mock_llm,
        candidates_limit=50,
        digest_size=30,
    )

    await recommender.recommend(
        session=mock_session,
        user_id=1,
        interests="news",
        channel_ids=[1, 2, 3],
    )

    # Should have 3 execute calls (one per channel)
    assert mock_session.execute.call_count == 3
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_recommender.py::test_recommend_diverse_pool_queries_each_channel -x -q`
Expected: FAIL (single query, not per-channel)

**Step 3: Commit**

```bash
git add tests/test_recommender.py
git commit -m "test: add failing tests for channel diversity"
```

---

### Task 2: Implement diverse pool and quality gate

**Files:**
- Modify: `core/recommender.py`

**Step 1: Add `quality_threshold` to `__init__`**

In `core/recommender.py`, update the `__init__` method (lines 37-49):

```python
class Recommender:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_provider: LLMProvider,
        candidates_limit: int = 50,
        digest_size: int = 30,
        provider_name: str = "openai",
        quality_threshold: float = 0.5,
    ):
        self.embedding_service = embedding_service
        self.llm_provider = llm_provider
        self.candidates_limit = candidates_limit
        self.digest_size = digest_size
        self.provider_name = provider_name
        self.quality_threshold = quality_threshold
```

Note: `digest_size` default changed from 5 to 30.

**Step 2: Replace Stage 1 (single query) with per-channel queries**

Replace lines 74-86 (the single pgvector query + dedup) with:

```python
        # Stage 1: per-channel pgvector similarity search (diverse pool)
        from math import ceil

        per_channel_limit = ceil(self.candidates_limit / len(channel_ids))
        all_candidates = []

        for ch_id in channel_ids:
            stmt = (
                select(Message)
                .where(Message.channel_id == ch_id)
                .where(Message.embedding.isnot(None))
            )
            if window_start:
                stmt = stmt.where(Message.date >= window_start)
            stmt = stmt.order_by(
                Message.embedding.cosine_distance(query_vector)
            ).limit(per_channel_limit)
            result = await session.execute(stmt)
            all_candidates.extend(result.scalars().all())

        candidates = deduplicate_candidates(all_candidates)
```

**Step 3: Add quality gate after LLM ranking**

Replace line 107:
```python
        return llm_result.ranked
```

With:
```python
        # Stage 3: quality gate — drop low-score items
        return [r for r in llm_result.ranked if r["score"] >= self.quality_threshold]
```

**Step 4: Run new tests**

Run: `venv/bin/python -m pytest tests/test_recommender.py -x -q -W error`
Expected: All pass

**Step 5: Fix existing test if needed**

The existing `test_recommend_calls_embedding_then_llm` sends `channel_ids=[1, 2]`, which means 2 execute calls now (not 1). Update:

The existing test mocks `mock_session.execute.return_value` (single return). Change to `side_effect` for two calls:

```python
    # Mock DB query result — one per channel
    mock_msg1 = MagicMock(id=1, text="ML news", channel_id=1, content_hash="h1", date=None)
    mock_msg2 = MagicMock(id=2, text="Crypto update", channel_id=1, content_hash="h2", date=None)
    mock_msg3 = MagicMock(id=3, text="Cat video", channel_id=2, content_hash="h3", date=None)

    result_ch1 = MagicMock()
    result_ch1.scalars.return_value.all.return_value = [mock_msg1, mock_msg2]
    result_ch2 = MagicMock()
    result_ch2.scalars.return_value.all.return_value = [mock_msg3]
    mock_session.execute.side_effect = [result_ch1, result_ch2]
```

Also the existing test uses `digest_size=2` — keep it (the quality gate won't filter since both scores are >= 0.5).

**Step 6: Run all tests**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 7: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 8: Commit**

```bash
git add core/recommender.py tests/test_recommender.py
git commit -m "feat(recommender): diverse per-channel pool + quality gate"
```

---

### Task 3: Update Recommender instantiation in bot and config

**Files:**
- Modify: `core/config.py` (if `digest_size` or `quality_threshold` is configurable — check first)
- Modify: any file that constructs `Recommender(...)` to pass updated defaults

**Step 1: Find all Recommender instantiations**

Run: `grep -rn "Recommender(" --include="*.py" .`

Check if `digest_size=5` is hardcoded anywhere. If so, remove the explicit `digest_size=5` so the new default (30) is used. Same for `quality_threshold`.

**Step 2: Run all tests**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 3: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 4: Commit (if changes needed)**

```bash
git add -u
git commit -m "chore: update Recommender instantiation for new defaults"
```

---

### Task 4: Verification

**Step 1: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 2: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 3: Manual test**

Reset last_digest_at and request a digest:
```sql
docker exec tematch-postgres-1 psql -U tematch -d tematch -c "UPDATE users SET last_digest_at = NULL WHERE telegram_id = 177363488;"
```
Then send `/digest` in Telegram. Verify:
- Messages from multiple channels appear
- Low-relevance items are filtered out
- Digest may have more than 5 items (paginated)
