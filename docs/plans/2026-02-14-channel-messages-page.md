# Channel Messages Page — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let users click a channel in the web dashboard to see a paginated table of all its messages with relevance scores.

**Architecture:** New FastAPI endpoint returns paginated messages with pgvector relevance scores. New React page renders a cyber-table. Channel list titles become clickable links.

**Tech Stack:** FastAPI, SQLAlchemy 2 async, pgvector cosine_distance, React 19, React Router 7, TypeScript

---

### Task 1: Backend — channel messages endpoint

**Files:**
- Modify: `web/routers/channels.py`
- Test: `tests/test_web_channels.py` (create)

**Step 1: Write the failing test**

Create `tests/test_web_channels.py`:

```python
"""Tests for channel messages API endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from web.main import app


def _user_cookie():
    from web.auth import create_jwt
    return {"auth_token": create_jwt(telegram_id=999, secret="test-secret-that-is-32-bytes-ok!")}


@pytest.fixture(autouse=True)
def _mock_settings():
    with patch("web.main._settings") as mock:
        mock.ADMIN_TELEGRAM_ID = 999
        mock.WEB_JWT_SECRET = "test-secret-that-is-32-bytes-ok!"
        yield mock


@pytest.fixture(autouse=True)
def _mock_deps():
    from core.models import User
    from web import deps

    user = User(telegram_id=999)
    user.id = 1
    user.interests_embedding = None

    async def _fake_user():
        return user

    mock_session = AsyncMock()

    # Default: execute returns empty result
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_result.all.return_value = []
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = []
    mock_result.scalars.return_value = mock_scalars
    mock_session.execute.return_value = mock_result

    async def _fake_session():
        return mock_session

    app.dependency_overrides[deps.get_session] = _fake_session
    app.dependency_overrides[deps.get_current_user] = _fake_user
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_channel_messages_not_subscribed():
    """Returns 404 when user is not subscribed to the channel."""
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_user_cookie()
    ) as client:
        resp = await client.get("/api/users/me/channels/999/messages")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_channel_messages_returns_shape():
    """Returns correct response shape with pagination metadata."""
    from core.models import User, UserChannel
    from web import deps

    # Create user with subscription
    user = User(telegram_id=999)
    user.id = 1
    user.interests_embedding = None

    mock_session = AsyncMock()

    # First execute: subscription check → returns a UserChannel
    uc = MagicMock()
    sub_result = MagicMock()
    sub_result.scalar_one_or_none.return_value = uc

    # Second execute: channel info
    ch = MagicMock()
    ch.id = 5
    ch.title = "Test Channel"
    ch.username = "testchan"
    ch_result = MagicMock()
    ch_result.scalar_one_or_none.return_value = ch

    # Third execute: count → 0
    count_result = MagicMock()
    count_result.scalar_one.return_value = 0

    # Fourth execute: messages → []
    msg_result = MagicMock()
    msg_result.all.return_value = []

    mock_session.execute.side_effect = [sub_result, ch_result, count_result, msg_result]

    async def _fake_user():
        return user

    async def _fake_session():
        return mock_session

    app.dependency_overrides[deps.get_session] = _fake_session
    app.dependency_overrides[deps.get_current_user] = _fake_user

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_user_cookie()
    ) as client:
        resp = await client.get("/api/users/me/channels/5/messages")
    assert resp.status_code == 200
    data = resp.json()
    assert "channel" in data
    assert "messages" in data
    assert "total" in data
    assert "page" in data
    assert data["channel"]["title"] == "Test Channel"
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_web_channels.py -x -q`
Expected: FAIL (404 endpoint not found or route doesn't exist)

**Step 3: Implement the endpoint**

Add to `web/routers/channels.py`:

```python
from fastapi import Query

@router.get("/{channel_id}/messages")
async def channel_messages(
    channel_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
    user: User = Depends(get_current_user),
):
    # Verify subscription
    sub_stmt = select(UserChannel).where(
        UserChannel.user_id == user.id,
        UserChannel.channel_id == channel_id,
    )
    sub = (await session.execute(sub_stmt)).scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="Channel not in subscriptions")

    # Get channel info
    ch = (await session.execute(
        select(Channel).where(Channel.id == channel_id)
    )).scalar_one_or_none()

    # Total count
    count_stmt = select(func.count(Message.id)).where(Message.channel_id == channel_id)
    total = (await session.execute(count_stmt)).scalar_one()

    # Paginated messages with optional relevance
    offset = (page - 1) * per_page

    if user.interests_embedding is not None:
        stmt = (
            select(
                Message.id,
                Message.text,
                Message.date,
                Message.has_media,
                (Message.embedding.isnot(None)).label("has_embedding"),
                (1 - Message.embedding.cosine_distance(user.interests_embedding)).label("relevance"),
            )
            .where(Message.channel_id == channel_id)
            .order_by(Message.date.desc())
            .offset(offset)
            .limit(per_page)
        )
    else:
        stmt = (
            select(
                Message.id,
                Message.text,
                Message.date,
                Message.has_media,
                (Message.embedding.isnot(None)).label("has_embedding"),
            )
            .where(Message.channel_id == channel_id)
            .order_by(Message.date.desc())
            .offset(offset)
            .limit(per_page)
        )

    rows = (await session.execute(stmt)).all()

    return {
        "channel": {
            "id": ch.id,
            "title": ch.title or ch.username,
            "username": ch.username,
        },
        "messages": [
            {
                "id": r.id,
                "text": r.text[:200] if r.text else "",
                "date": r.date.isoformat() if r.date else None,
                "has_embedding": r.has_embedding,
                "relevance": round(r.relevance, 3) if hasattr(r, "relevance") and r.relevance is not None else None,
                "has_media": r.has_media,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }
```

Also add `Query` to the imports at the top of the file:
```python
from fastapi import APIRouter, Depends, HTTPException, Query
```

**Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_web_channels.py -x -q`
Expected: PASS

**Step 5: Lint**

Run: `venv/bin/ruff check .`
Expected: All checks passed

**Step 6: Commit**

```bash
git add web/routers/channels.py tests/test_web_channels.py
git commit -m "feat(web): add GET /api/users/me/channels/:id/messages endpoint"
```

---

### Task 2: Frontend — make channel titles clickable

**Files:**
- Modify: `web/frontend/src/components/ChannelList.tsx`

**Step 1: Add Link import and wrap channel title**

Update `ChannelList.tsx` — add `Link` from react-router-dom and make channel title a link:

```tsx
import { Link } from 'react-router-dom';
import { apiFetch } from '../api';

interface Channel {
  id: number;
  title: string;
  username: string | null;
  message_count: number;
  added_at: string | null;
}

export default function ChannelList({ channels, onRefresh }: { channels: Channel[]; onRefresh: () => void }) {
  const unsubscribe = async (id: number) => {
    if (!confirm('Unsubscribe from this channel?')) return;
    await apiFetch(`/api/users/me/channels/${id}`, { method: 'DELETE' });
    onRefresh();
  };

  return (
    <table className="cyber-table">
      <thead>
        <tr>
          <th>Channel</th>
          <th>Messages</th>
          <th>Added</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {channels.map((ch) => (
          <tr key={ch.id}>
            <td>
              <Link to={`/channels/${ch.id}`} style={{ color: 'var(--text-primary)', textDecoration: 'none', borderBottom: '1px solid var(--border-dim)', transition: 'border-color 0.2s' }}
                onMouseEnter={(e) => (e.currentTarget.style.borderBottomColor = 'var(--cyan)')}
                onMouseLeave={(e) => (e.currentTarget.style.borderBottomColor = 'var(--border-dim)')}>
                {ch.title}
              </Link>
              {ch.username && <span className="cyber-mono" style={{ color: 'var(--text-muted)', marginLeft: '0.5rem', fontSize: '0.8rem' }}>@{ch.username}</span>}
            </td>
            <td className="cyber-mono">{ch.message_count}</td>
            <td>{ch.added_at ? new Date(ch.added_at).toLocaleDateString() : '—'}</td>
            <td>
              <button onClick={() => unsubscribe(ch.id)} className="cyber-btn cyber-btn-danger" style={{ fontSize: '0.65rem', padding: '0.25rem 0.75rem' }}>
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

**Step 2: Commit**

```bash
git add web/frontend/src/components/ChannelList.tsx
git commit -m "feat(web): make channel titles clickable links"
```

---

### Task 3: Frontend — ChannelMessages page

**Files:**
- Create: `web/frontend/src/pages/ChannelMessages.tsx`
- Modify: `web/frontend/src/App.tsx`

**Step 1: Create the ChannelMessages page**

Create `web/frontend/src/pages/ChannelMessages.tsx`:

```tsx
import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { apiFetch } from '../api';

interface MsgRow {
  id: number;
  text: string;
  date: string | null;
  has_embedding: boolean;
  relevance: number | null;
  has_media: boolean;
}

interface ChannelMessagesResponse {
  channel: { id: number; title: string; username: string | null };
  messages: MsgRow[];
  total: number;
  page: number;
  per_page: number;
}

export default function ChannelMessages() {
  const { id } = useParams<{ id: string }>();
  const [data, setData] = useState<ChannelMessagesResponse | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const resp = await apiFetch<ChannelMessagesResponse>(
      `/api/users/me/channels/${id}/messages?page=${page}&per_page=50`
    );
    setData(resp);
    setLoading(false);
  }, [id, page]);

  useEffect(() => { load(); }, [load]);

  if (loading && !data) return (
    <p className="cyber-mono" style={{ color: 'var(--text-muted)' }}>Loading...</p>
  );

  if (!data) return null;

  const totalPages = Math.ceil(data.total / data.per_page);

  return (
    <div className="max-w-5xl space-y-6">
      <div className="flex items-center gap-4 animate-in">
        <Link to="/dashboard" className="cyber-btn" style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}>
          ← Back
        </Link>
        <h2 className="cyber-heading-lg" style={{ fontSize: '1.2rem' }}>
          {data.channel.title}
          {data.channel.username && (
            <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.8rem', marginLeft: '0.75rem' }}>
              @{data.channel.username}
            </span>
          )}
        </h2>
        <span className="cyber-mono" style={{ color: 'var(--text-muted)', fontSize: '0.75rem', marginLeft: 'auto' }}>
          {data.total} messages
        </span>
      </div>

      <section className="cyber-card animate-in animate-in-1" style={{ padding: '1.5rem' }}>
        <table className="cyber-table">
          <thead>
            <tr>
              <th style={{ width: '50%' }}>Message</th>
              <th>Date</th>
              <th style={{ textAlign: 'center' }}>Emb</th>
              <th style={{ textAlign: 'center' }}>Relevance</th>
              <th style={{ textAlign: 'center' }}>Media</th>
            </tr>
          </thead>
          <tbody>
            {data.messages.map((m) => (
              <tr key={m.id}>
                <td style={{ color: 'var(--text-primary)', fontSize: '0.8rem', lineHeight: 1.4, maxWidth: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {m.text}
                </td>
                <td className="cyber-mono" style={{ fontSize: '0.75rem', whiteSpace: 'nowrap' }}>
                  {m.date ? new Date(m.date).toLocaleString() : '—'}
                </td>
                <td style={{ textAlign: 'center' }}>
                  <span className={`status-dot ${m.has_embedding ? 'status-green' : 'status-red'}`} />
                </td>
                <td className="cyber-mono" style={{ textAlign: 'center', color: m.relevance != null && m.relevance > 0.3 ? 'var(--neon-green)' : 'var(--text-muted)' }}>
                  {m.relevance != null ? `${Math.round(m.relevance * 100)}%` : '—'}
                </td>
                <td style={{ textAlign: 'center', opacity: m.has_media ? 1 : 0.2 }}>
                  📎
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-4" style={{ marginTop: '1.25rem' }}>
            <button
              className="cyber-btn"
              style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Prev
            </button>
            <span className="cyber-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              {page} / {totalPages}
            </span>
            <button
              className="cyber-btn"
              style={{ fontSize: '0.7rem', padding: '0.3rem 0.75rem' }}
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        )}
      </section>
    </div>
  );
}
```

**Step 2: Add route to App.tsx**

In `App.tsx`, add import and route:

```tsx
import ChannelMessages from './pages/ChannelMessages';
```

Add inside the authenticated `<Route element={...}>` group, after the Dashboard route:

```tsx
<Route path="/channels/:id" element={<ChannelMessages />} />
```

**Step 3: Build frontend**

```bash
cd web/frontend && npm run build
```

Expected: Build succeeds, output in `web/frontend/dist/`

**Step 4: Commit**

```bash
git add web/frontend/src/pages/ChannelMessages.tsx web/frontend/src/App.tsx web/frontend/dist/
git commit -m "feat(web): channel messages page with pagination and relevance scores"
```

---

### Task 4: Verify everything

**Step 1: Lint backend**

Run: `venv/bin/ruff check .`
Expected: All checks passed

**Step 2: Run all tests**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 3: Manual verification**

1. Restart web server
2. Open dashboard → channel list shows clickable titles
3. Click a channel → navigates to `/channels/:id`
4. Table shows messages with text, date, embedding dot, relevance %, media icon
5. Pagination works (if > 50 messages)
6. Back button returns to dashboard

---

### Key Files Summary

| File | Action |
|---|---|
| `web/routers/channels.py` | ADD messages endpoint |
| `tests/test_web_channels.py` | CREATE test file |
| `web/frontend/src/components/ChannelList.tsx` | ADD Link to channel title |
| `web/frontend/src/pages/ChannelMessages.tsx` | CREATE page |
| `web/frontend/src/App.tsx` | ADD route |
