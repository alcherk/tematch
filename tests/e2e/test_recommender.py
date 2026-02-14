"""E2E tests for recommender pipeline: embedding cache, dedup integration, LLM ranking."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.embeddings import EmbeddingResult
from core.llm.base import LLMResult
from core.recommender import Recommender, deduplicate_candidates


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_cached_embedding_skips_api_call(_mock_log):
    """Feature 15: passing interests_embedding bypasses embed_text call."""
    mock_session = AsyncMock()
    mock_embed = AsyncMock()
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[{"message_id": 1, "score": 0.9}],
        tokens_in=100, tokens_out=50,
    )

    mock_result = MagicMock()
    mock_msg = MagicMock(id=1, text="ML news", content_hash="h1", date=None)
    mock_result.scalars.return_value.all.return_value = [mock_msg]
    mock_session.execute.return_value = mock_result

    recommender = Recommender(embedding_service=mock_embed, llm_provider=mock_llm)

    cached = [0.1] * 1536
    await recommender.recommend(
        session=mock_session, user_id=1, interests="ML",
        channel_ids=[1], interests_embedding=cached,
    )

    mock_embed.embed_text.assert_not_called()


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_no_cached_embedding_calls_api(_mock_log):
    """Feature 15: without cached embedding, embed_text is called."""
    mock_session = AsyncMock()
    mock_embed = AsyncMock()
    mock_embed.embed_text.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536], tokens=10,
    )
    mock_llm = AsyncMock()
    mock_llm.rank_messages.return_value = LLMResult(
        ranked=[{"message_id": 1, "score": 0.9}],
        tokens_in=100, tokens_out=50,
    )

    mock_result = MagicMock()
    mock_msg = MagicMock(id=1, text="ML news", content_hash="h1", date=None)
    mock_result.scalars.return_value.all.return_value = [mock_msg]
    mock_session.execute.return_value = mock_result

    recommender = Recommender(embedding_service=mock_embed, llm_provider=mock_llm)

    await recommender.recommend(
        session=mock_session, user_id=1, interests="ML",
        channel_ids=[1],
    )

    mock_embed.embed_text.assert_called_once_with("ML")


def test_dedup_preserves_messages_without_hash():
    """Feature 10: messages with content_hash=None are all kept."""
    msg1 = MagicMock(id=1, content_hash=None, date=datetime(2026, 1, 1))
    msg2 = MagicMock(id=2, content_hash=None, date=datetime(2026, 1, 2))

    result = deduplicate_candidates([msg1, msg2])
    assert len(result) == 2


def test_dedup_keeps_earliest_of_same_hash():
    """Feature 10: among duplicates, the earliest by date survives."""
    early = MagicMock(id=1, content_hash="same", date=datetime(2026, 1, 1, 8, 0))
    late = MagicMock(id=2, content_hash="same", date=datetime(2026, 1, 1, 20, 0))

    result = deduplicate_candidates([late, early])
    assert len(result) == 1
    assert result[0].id == 1
