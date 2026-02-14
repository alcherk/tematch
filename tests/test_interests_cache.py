from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.llm.base import LLMResult
from core.recommender import Recommender


@pytest.mark.asyncio
@patch("core.recommender.log_usage", new_callable=AsyncMock)
async def test_recommend_uses_cached_interests_embedding(_mock_log):
    mock_session = AsyncMock()
    mock_embedding = AsyncMock()
    mock_llm = AsyncMock()

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
