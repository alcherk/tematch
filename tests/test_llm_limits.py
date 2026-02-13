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
