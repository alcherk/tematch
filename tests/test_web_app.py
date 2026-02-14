"""Tests for FastAPI app basics: health, auth endpoint, deps."""

import pytest
from httpx import ASGITransport, AsyncClient

from web.deps import get_session
from web.main import app


async def _mock_session():
    yield None


@pytest.fixture(autouse=True)
def _override_session():
    app.dependency_overrides[get_session] = _mock_session
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_api_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_me_unauthenticated():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
