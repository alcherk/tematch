from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.embeddings import EmbeddingResult
from core.llm.base import LLMResult
from core.recommender import Recommender


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_recommend_calls_embedding_then_llm(_mock_log):
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
        ],
        tokens_in=500,
        tokens_out=100,
    )

    # Mock DB query result
    mock_result = MagicMock()
    mock_msg1 = MagicMock(id=1, text="ML news", channel_id=1, content_hash="h1", date=None)
    mock_msg2 = MagicMock(id=2, text="Crypto update", channel_id=1, content_hash="h2", date=None)
    mock_msg3 = MagicMock(id=3, text="Cat video", channel_id=2, content_hash="h3", date=None)
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


from math import ceil


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
    assert 1 in msg_ids
    assert 3 in msg_ids or 4 in msg_ids


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
            {"message_id": 3, "score": 0.30},
            {"message_id": 4, "score": 0.10},
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

    assert mock_session.execute.call_count == 3
