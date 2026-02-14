"""Tests for admin API endpoints (mocked DB)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from web.main import app


def _admin_cookie():
    """Create a valid JWT cookie for the admin user."""
    from web.auth import create_jwt

    return {"auth_token": create_jwt(telegram_id=999, secret="test-secret-that-is-32-bytes-ok!")}


@pytest.fixture(autouse=True)
def _mock_settings():
    """Override settings for tests."""
    with patch("web.main._settings") as mock:
        mock.ADMIN_TELEGRAM_ID = 999
        mock.WEB_JWT_SECRET = "test-secret-that-is-32-bytes-ok!"
        mock.DAILY_TOKEN_BUDGET = 500_000
        yield mock


def _make_mock_session():
    """Create a mock async session that returns sensible defaults."""
    session = AsyncMock()

    # session.execute() returns a result with .scalar_one() / .scalar_one_or_none() / .scalars() / .all()
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = 0
    mock_result.scalar_one_or_none.return_value = 0
    mock_result.all.return_value = []
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars

    session.execute.return_value = mock_result
    return session


@pytest.fixture(autouse=True)
def _mock_deps():
    """Override DB dependency with mock."""
    from core.models import User
    from web import deps

    admin_user = User(telegram_id=999)
    admin_user.id = 1

    async def _fake_admin():
        return admin_user

    mock_session = _make_mock_session()

    async def _fake_session():
        return mock_session

    app.dependency_overrides[deps.get_session] = _fake_session
    app.dependency_overrides[deps.get_current_user] = _fake_admin
    app.dependency_overrides[deps.require_admin] = _fake_admin
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_admin_stats_returns_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_admin_cookie()
    ) as client:
        resp = await client.get("/api/admin/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "users" in data
    assert "channels" in data
    assert "messages_today" in data


@pytest.mark.asyncio
async def test_admin_costs_returns_list():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_admin_cookie()
    ) as client:
        resp = await client.get("/api/admin/costs?period=7d")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_admin_health_returns_shape():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_admin_cookie()
    ) as client:
        resp = await client.get("/api/admin/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "channels" in data
    assert "token_budget" in data
