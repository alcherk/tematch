from unittest.mock import AsyncMock, MagicMock

import pytest

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
