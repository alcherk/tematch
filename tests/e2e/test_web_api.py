"""E2E test for web API against real Postgres."""

from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from core.models import Channel, User
from web.auth import create_jwt
from web.main import app


@pytest.mark.asyncio
async def test_admin_stats_with_real_db(session, session_factory):
    """Seed DB, hit /api/admin/stats, verify counts."""
    user = User(telegram_id=999_999)
    ch = Channel(telegram_id=888_001, title="TestChannel")
    session.add_all([user, ch])
    await session.commit()

    from web import deps

    async def _get_session():
        async with session_factory() as s:
            yield s

    # Patch settings and deps
    import web.main as wm

    wm._settings = MagicMock()
    wm._settings.ADMIN_TELEGRAM_ID = 999_999
    wm._settings.WEB_JWT_SECRET = "test-secret-that-is-32-bytes-ok!"
    wm._settings.DAILY_TOKEN_BUDGET = 500_000

    app.dependency_overrides[deps.get_session] = _get_session

    token = create_jwt(telegram_id=999_999, secret="test-secret-that-is-32-bytes-ok!")
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        cookies={"auth_token": token},
    ) as client:
        resp = await client.get("/api/admin/stats")

    app.dependency_overrides.clear()

    assert resp.status_code == 200
    data = resp.json()
    assert data["users"] >= 1
    assert data["channels"] >= 1
