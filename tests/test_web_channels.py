"""Tests for channels API endpoints (mocked DB)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from web.main import app


def _user_cookie():
    """Create a valid JWT cookie for a regular user."""
    from web.auth import create_jwt

    return {"auth_token": create_jwt(telegram_id=111, secret="test-secret-that-is-32-bytes-ok!")}


@pytest.fixture(autouse=True)
def _mock_settings():
    """Override settings for tests."""
    with patch("web.main._settings") as mock:
        mock.ADMIN_TELEGRAM_ID = 999
        mock.WEB_JWT_SECRET = "test-secret-that-is-32-bytes-ok!"
        mock.DAILY_TOKEN_BUDGET = 500_000
        yield mock


@pytest.fixture()
def mock_session():
    """Create a mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def _mock_deps(mock_session):
    """Override DB dependency with mock."""
    from core.models import User
    from web import deps

    user = User(telegram_id=111)
    user.id = 1
    user.interests_embedding = None

    async def _fake_user():
        return user

    async def _fake_session():
        return mock_session

    app.dependency_overrides[deps.get_session] = _fake_session
    app.dependency_overrides[deps.get_current_user] = _fake_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_channel_messages_not_subscribed(mock_session):
    """GET /api/users/me/channels/{id}/messages returns 404 when not subscribed."""
    # subscription check returns None
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_user_cookie()
    ) as client:
        resp = await client.get("/api/users/me/channels/5/messages")

    assert resp.status_code == 404
    assert resp.json()["detail"] == "Channel not in subscriptions"


@pytest.mark.asyncio
async def test_channel_messages_returns_shape(mock_session):
    """GET /api/users/me/channels/{id}/messages returns correct JSON shape."""
    # Build side_effect sequence for session.execute calls:
    # 1st call: subscription check -> returns a UserChannel mock
    sub_result = MagicMock()
    sub_mock = MagicMock()
    sub_mock.user_id = 1
    sub_mock.channel_id = 5
    sub_result.scalar_one_or_none.return_value = sub_mock

    # 2nd call: channel info -> returns a Channel mock
    ch_result = MagicMock()
    ch_mock = MagicMock()
    ch_mock.id = 5
    ch_mock.title = "Test Channel"
    ch_mock.username = "testchan"
    ch_result.scalar_one_or_none.return_value = ch_mock

    # 3rd call: count -> returns scalar_one = 0
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    # 4th call: messages -> returns all = []
    msgs_result = MagicMock()
    msgs_result.all.return_value = []

    mock_session.execute.side_effect = [sub_result, ch_result, count_result, msgs_result]

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_user_cookie()
    ) as client:
        resp = await client.get("/api/users/me/channels/5/messages")

    assert resp.status_code == 200
    data = resp.json()
    assert "channel" in data
    assert data["channel"]["id"] == 5
    assert data["channel"]["title"] == "Test Channel"
    assert data["channel"]["username"] == "testchan"
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert data["messages"] == []
    assert "total" in data
    assert data["total"] == 0
    assert "page" in data
    assert data["page"] == 1
    assert "per_page" in data
