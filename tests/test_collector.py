from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.channel_manager import get_active_channel_ids


@pytest.mark.asyncio
async def test_get_active_channel_ids():
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [100, 200, 300]
    mock_session.execute.return_value = mock_result

    ids = await get_active_channel_ids(mock_session)
    assert ids == [100, 200, 300]
