from unittest.mock import AsyncMock, MagicMock

import pytest

from core.llm_usage import get_daily_token_total, log_usage


@pytest.mark.asyncio
async def test_log_usage():
    mock_session = AsyncMock()
    mock_session.add = MagicMock()  # add() is synchronous in SQLAlchemy
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
