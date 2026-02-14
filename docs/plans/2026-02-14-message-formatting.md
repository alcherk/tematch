# Message Formatting Preservation — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve original Telegram message formatting (bold, italic, code, links, quotes, etc.) throughout the pipeline: collector stores HTML, digest renders it, web displays it.

**Architecture:** Add `text_html` nullable column to Message model. Collector converts Telethon entities to HTML via `telethon.extensions.html.unparse()`. Plain `text` stays for embeddings/hash/LLM. Resync backfills existing messages missing `text_html`. Digest formatter and web UI use `text_html` when available, fall back to escaped plain text.

**Tech Stack:** Python 3.9, SQLAlchemy 2, Alembic, Telethon, aiogram 3, React 19, FastAPI

---

### Task 1: Add `text_html` column to Message model

**Files:**
- Modify: `core/models.py:72-88` (Message class)

**Step 1: Add column to model**

In `core/models.py`, add `text_html` to the `Message` class after `text`:

```python
text_html: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

**Step 2: Run lint**

Run: `venv/bin/ruff check .`
Expected: Clean (0 errors)

**Step 3: Run tests to confirm nothing breaks**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 4: Commit**

```bash
git add core/models.py
git commit -m "feat(models): add text_html column to Message"
```

---

### Task 2: Alembic migration for `text_html`

**Files:**
- Create: `alembic/versions/b4c2d3e5f6a7_add_text_html_to_messages.py`

**Step 1: Create migration**

Follow the pattern from `alembic/versions/a3b1c2d3e4f5_add_has_media_to_messages.py`:

```python
"""add text_html to messages

Revision ID: b4c2d3e5f6a7
Revises: a3b1c2d3e4f5
Create Date: 2026-02-14 20:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b4c2d3e5f6a7"
down_revision: Union[str, Sequence[str], None] = "a3b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "messages",
        sa.Column("text_html", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("messages", "text_html")
```

**Step 2: Apply migration**

Run: `venv/bin/python -m alembic upgrade head`
Expected: `Running upgrade a3b1c2d3e4f5 -> b4c2d3e5f6a7, add text_html to messages`

Note: Docker (PostgreSQL) must be running.

**Step 3: Verify column exists**

Run: `docker exec tematch-db psql -U tematch -d tematch -c "\d messages" | grep text_html`
Expected: `text_html | text |           |          |`

**Step 4: Commit**

```bash
git add alembic/versions/b4c2d3e5f6a7_add_text_html_to_messages.py
git commit -m "feat(db): add text_html migration"
```

---

### Task 3: Collector — capture entities and produce HTML

**Files:**
- Modify: `collector/handlers.py` (handle_new_message)
- Modify: `collector/main.py` (live handler)
- Modify: `collector/resync.py` (resync loop)
- Test: `tests/test_collector_html.py`

**Step 1: Write failing tests**

Create `tests/test_collector_html.py`:

```python
"""Tests for text_html handling in collector."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.handlers import handle_new_message


def _mock_session(channel=None, msg_exists=False):
    session = AsyncMock()
    # 1st execute: channel lookup
    ch_result = MagicMock()
    ch_result.scalar_one_or_none.return_value = channel
    # 2nd execute: message exists check
    exists_result = MagicMock()
    exists_result.scalar_one_or_none.return_value = 1 if msg_exists else None
    session.execute.side_effect = [ch_result, exists_result]
    return session


def _make_channel(id=5):
    ch = MagicMock()
    ch.id = id
    ch.last_fetched_at = None
    return ch


@pytest.mark.asyncio
async def test_handle_new_message_stores_text_html():
    """When entities are provided, text_html should be set."""
    ch = _make_channel()
    session = _mock_session(channel=ch)

    from datetime import datetime
    from telethon.tl.types import MessageEntityBold

    entities = [MessageEntityBold(offset=0, length=5)]
    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Hello world test message",
        date=datetime(2026, 2, 14),
        entities=entities,
    )

    added_msg = session.add.call_args[0][0]
    assert added_msg.text_html is not None
    assert "<strong>" in added_msg.text_html


@pytest.mark.asyncio
async def test_handle_new_message_no_entities_no_html():
    """When no entities provided, text_html should be None."""
    ch = _make_channel()
    session = _mock_session(channel=ch)

    from datetime import datetime

    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Plain text message here",
        date=datetime(2026, 2, 14),
    )

    added_msg = session.add.call_args[0][0]
    assert added_msg.text_html is None


@pytest.mark.asyncio
async def test_handle_existing_message_backfills_html():
    """When message already exists but text_html is NULL, update it."""
    ch = _make_channel()
    session = AsyncMock()

    # 1st execute: channel lookup
    ch_result = MagicMock()
    ch_result.scalar_one_or_none.return_value = ch
    # 2nd execute: message exists check — return the message ID
    exists_result = MagicMock()
    exists_result.scalar_one_or_none.return_value = 1
    # 3rd execute: fetch message for backfill
    msg_obj = MagicMock()
    msg_obj.text_html = None
    msg_result = MagicMock()
    msg_result.scalar_one_or_none.return_value = msg_obj

    session.execute.side_effect = [ch_result, exists_result, msg_result]

    from datetime import datetime
    from telethon.tl.types import MessageEntityItalic

    entities = [MessageEntityItalic(offset=0, length=5)]
    await handle_new_message(
        session=session,
        channel_telegram_id=123,
        message_id=1,
        text="Hello world test message",
        date=datetime(2026, 2, 14),
        entities=entities,
    )

    assert msg_obj.text_html is not None
    assert "<em>" in msg_obj.text_html
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_collector_html.py -x -q`
Expected: FAIL (entities parameter not accepted)

**Step 3: Implement — modify `handle_new_message`**

In `collector/handlers.py`, add `entities` parameter and HTML generation:

```python
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telethon.extensions.html import unparse as html_unparse

from core.content_hash import compute_content_hash
from core.models import Channel, Message

logger = logging.getLogger(__name__)


async def handle_new_message(
    session: AsyncSession,
    channel_telegram_id: int,
    message_id: int,
    text: str,
    date: datetime,
    embedding_buffer=None,
    reply_to_msg_id=None,
    has_media: bool = False,
    entities=None,
):
    if not text or len(text.strip()) < 20:
        return

    # Convert entities to HTML
    text_html: Optional[str] = None
    if entities:
        try:
            text_html = html_unparse(text, entities)
        except Exception:
            logger.debug("Failed to unparse entities, skipping HTML")

    # Find channel in DB
    stmt = select(Channel).where(Channel.telegram_id == channel_telegram_id)
    result = await session.execute(stmt)
    channel = result.scalar_one_or_none()
    if not channel:
        return

    # Check if message already exists
    exists_stmt = select(Message.id).where(
        Message.channel_id == channel.id,
        Message.telegram_msg_id == message_id,
    )
    exists = (await session.execute(exists_stmt)).scalar_one_or_none()
    if exists:
        # Backfill text_html if missing
        if text_html:
            backfill_stmt = select(Message).where(
                Message.channel_id == channel.id,
                Message.telegram_msg_id == message_id,
            )
            msg_obj = (await session.execute(backfill_stmt)).scalar_one_or_none()
            if msg_obj and not msg_obj.text_html:
                msg_obj.text_html = text_html
                await session.commit()
        return

    content_hash = compute_content_hash(text)

    # Strip timezone — DB column is TIMESTAMP WITHOUT TIME ZONE
    naive_date = date.replace(tzinfo=None) if date and date.tzinfo else date

    msg = Message(
        channel_id=channel.id,
        telegram_msg_id=message_id,
        text=text,
        text_html=text_html,
        date=naive_date,
        content_hash=content_hash,
        reply_to_msg_id=reply_to_msg_id,
        has_media=has_media,
    )
    session.add(msg)
    await session.commit()
    await session.refresh(msg)

    # Add to embedding buffer for batched processing
    if embedding_buffer is not None:
        embedding_buffer.add(message_id=msg.id, text=text)

    channel.last_fetched_at = datetime.utcnow()
    await session.commit()
```

**Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_collector_html.py -x -q -W error`
Expected: 3 passed

**Step 5: Update live handler in `collector/main.py`**

Add `entities=event.message.entities` to the `handle_new_message` call (line 60-69):

```python
await handle_new_message(
    session=session,
    channel_telegram_id=chat.id,
    message_id=event.id,
    text=event.raw_text,
    date=event.date,
    embedding_buffer=embedding_buffer,
    reply_to_msg_id=reply_to_msg_id,
    has_media=event.media is not None,
    entities=event.message.entities,
)
```

**Step 6: Update resync in `collector/resync.py`**

Add `entities=msg.entities` to the `handle_new_message` call (around line 88-97):

```python
await handle_new_message(
    session=session,
    channel_telegram_id=entity if isinstance(entity, int) else channel.telegram_id,
    message_id=msg.id,
    text=msg.text,
    date=msg.date,
    embedding_buffer=embedding_buffer,
    reply_to_msg_id=reply_to_msg_id,
    has_media=msg.media is not None,
    entities=msg.entities,
)
```

**Step 7: Run all tests**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 8: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 9: Commit**

```bash
git add collector/handlers.py collector/main.py collector/resync.py tests/test_collector_html.py
git commit -m "feat(collector): capture Telegram entities and store text_html"
```

---

### Task 4: Digest formatter — use `text_html` when available

**Files:**
- Modify: `bot/formatters.py` (_format_single_item, format_recommendation)
- Test: `tests/test_formatters.py`

**Step 1: Write failing tests**

Add to `tests/test_formatters.py`:

```python
# --- text_html support ---


def _make_msg_with_html(text="Hello world", text_html=None, telegram_msg_id=10):
    msg = MagicMock()
    msg.text = text
    msg.text_html = text_html
    msg.telegram_msg_id = telegram_msg_id
    msg.has_media = False
    return msg


def test_format_digest_uses_text_html_when_available():
    """When msg.text_html is set, digest should use it directly (no escape)."""
    msg = _make_msg_with_html(
        text="Hello bold",
        text_html="Hello <strong>bold</strong>",
    )
    ch = _make_channel(username="chan")
    ch.title = "Test Channel"
    item = DigestItem(index=1, msg=msg, channel=ch, score=0.8, rec_id=100)
    result = format_digest_page([item])
    assert "<strong>bold</strong>" in result


def test_format_digest_falls_back_to_escaped_text():
    """When msg.text_html is None, digest should escape plain text."""
    msg = _make_msg_with_html(
        text="Use <b>tag</b>",
        text_html=None,
    )
    ch = _make_channel(username="chan")
    ch.title = "Test Channel"
    item = DigestItem(index=1, msg=msg, channel=ch, score=0.8, rec_id=100)
    result = format_digest_page([item])
    assert "&lt;b&gt;" in result


def test_format_recommendation_uses_text_html():
    """format_recommendation should use text_html when available."""
    ch = _make_channel(username="chan")
    msg = _make_msg_with_html(
        text="Plain text",
        text_html="<em>Italic</em> text",
    )
    result = format_recommendation(msg, ch, score=0.9, thread_messages=None)
    assert "<em>Italic</em>" in result
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_formatters.py::test_format_digest_uses_text_html_when_available -x -q`
Expected: FAIL

**Step 3: Implement — modify `_format_single_item`**

In `bot/formatters.py`, update `_format_single_item` body section (line 69):

From:
```python
parts.append(html_escape(_truncate(item.msg.text, MAX_BODY_LEN)))
```

To:
```python
body_html = getattr(item.msg, "text_html", None)
if body_html:
    parts.append(_truncate(body_html, MAX_BODY_LEN))
else:
    parts.append(html_escape(_truncate(item.msg.text, MAX_BODY_LEN)))
```

Also update thread snippet sections (lines 64-66 and 73-75) to use `text_html`:

Parents:
```python
for parent in item.thread["parents"]:
    p_html = getattr(parent, "text_html", None)
    snippet = _truncate(p_html or parent.text, MAX_THREAD_SNIPPET_LEN)
    if not p_html:
        snippet = html_escape(snippet)
    parts.append(f"  └ {snippet}")
```

Children:
```python
for child in item.thread["children"]:
    c_html = getattr(child, "text_html", None)
    snippet = _truncate(c_html or child.text, MAX_THREAD_SNIPPET_LEN)
    if not c_html:
        snippet = html_escape(snippet)
    parts.append(f"  └ {snippet}")
```

Update `format_recommendation` similarly (line 132):

From:
```python
parts.append(f"\n{_truncate(msg.text, MAX_TEXT_LEN)}")
```

To:
```python
msg_html = getattr(msg, "text_html", None)
if msg_html:
    parts.append(f"\n{_truncate(msg_html, MAX_TEXT_LEN)}")
else:
    parts.append(f"\n{_truncate(msg.text, MAX_TEXT_LEN)}")
```

**Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_formatters.py -x -q -W error`
Expected: All pass (new + existing)

**Step 5: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 6: Commit**

```bash
git add bot/formatters.py tests/test_formatters.py
git commit -m "feat(digest): use text_html for formatted output"
```

---

### Task 5: Web API — include `text_html` in response

**Files:**
- Modify: `web/routers/channels.py` (channel_messages endpoint)
- Test: `tests/test_web_channels.py`

**Step 1: Write failing test**

Add to `tests/test_web_channels.py`:

```python
@pytest.mark.asyncio
async def test_channel_messages_includes_text_html(mock_session):
    """Response should include text_html field."""
    sub_result = MagicMock()
    sub_mock = MagicMock()
    sub_mock.user_id = 1
    sub_mock.channel_id = 5
    sub_result.scalar_one_or_none.return_value = sub_mock

    ch_result = MagicMock()
    ch_mock = MagicMock()
    ch_mock.id = 5
    ch_mock.title = "Test Channel"
    ch_mock.username = "testchan"
    ch_result.scalar_one_or_none.return_value = ch_mock

    count_result = MagicMock()
    count_result.scalar_one.return_value = 1

    msg_row = MagicMock()
    msg_row.id = 10
    msg_row.text = "Hello bold"
    msg_row.text_html = "Hello <strong>bold</strong>"
    msg_row.date = None
    msg_row.has_embedding = True
    msg_row.has_media = False
    msgs_result = MagicMock()
    msgs_result.all.return_value = [msg_row]

    mock_session.execute.side_effect = [sub_result, ch_result, count_result, msgs_result]

    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", cookies=_user_cookie()
    ) as client:
        resp = await client.get("/api/users/me/channels/5/messages")

    assert resp.status_code == 200
    data = resp.json()
    msg = data["messages"][0]
    assert "text_html" in msg
    assert msg["text_html"] == "Hello <strong>bold</strong>"
```

**Step 2: Run test to verify it fails**

Run: `venv/bin/python -m pytest tests/test_web_channels.py::test_channel_messages_includes_text_html -x -q`
Expected: FAIL (text_html not in response)

**Step 3: Implement — add `text_html` to query and response**

In `web/routers/channels.py`, add `Message.text_html` to both SELECT variants (lines 75-98):

With relevance:
```python
stmt = (
    select(
        Message.id,
        Message.text,
        Message.text_html,
        Message.date,
        Message.has_media,
        (Message.embedding.isnot(None)).label("has_embedding"),
        (1 - Message.embedding.cosine_distance(user.interests_embedding)).label(
            "relevance"
        ),
    )
    .where(Message.channel_id == channel_id)
    .order_by(Message.date.desc())
    .offset(offset)
    .limit(per_page)
)
```

Without relevance:
```python
stmt = (
    select(
        Message.id,
        Message.text,
        Message.text_html,
        Message.date,
        Message.has_media,
        (Message.embedding.isnot(None)).label("has_embedding"),
    )
    .where(Message.channel_id == channel_id)
    .order_by(Message.date.desc())
    .offset(offset)
    .limit(per_page)
)
```

Add to response dict (line 115):
```python
"text_html": r.text_html if r.text_html else None,
```

**Step 4: Run tests to verify they pass**

Run: `venv/bin/python -m pytest tests/test_web_channels.py -x -q -W error`
Expected: All pass

**Step 5: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 6: Commit**

```bash
git add web/routers/channels.py tests/test_web_channels.py
git commit -m "feat(web): include text_html in channel messages API"
```

---

### Task 6: Frontend — render formatted HTML with DOMPurify

**Files:**
- Modify: `web/frontend/src/pages/ChannelMessages.tsx`
- Modify: `web/frontend/package.json` (add dompurify dependency)

**Step 1: Install DOMPurify**

Run: `cd web/frontend && npm install dompurify && npm install -D @types/dompurify`

DOMPurify provides defense-in-depth sanitization. The HTML is generated server-side from Telethon entities (not user input), but sanitizing on the client adds an extra safety layer.

**Step 2: Add `text_html` to `MsgRow` interface**

```typescript
interface MsgRow {
  id: number;
  text: string;
  text_html: string | null;
  date: string | null;
  has_embedding: boolean;
  relevance: number | null;
  has_media: boolean;
}
```

**Step 3: Render sanitized HTML when available**

Import DOMPurify at top:
```typescript
import DOMPurify from 'dompurify';
```

Replace the text cell content (line 94, currently `{m.text}`) with:

```tsx
{m.text_html ? (
  <span dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(m.text_html) }} />
) : (
  m.text
)}
```

**Step 4: Verify frontend builds**

Run: `cd web/frontend && npm run build`
Expected: Build succeeds with no errors

**Step 5: Commit**

```bash
git add web/frontend/src/pages/ChannelMessages.tsx web/frontend/package.json web/frontend/package-lock.json
git commit -m "feat(web): render formatted text_html in channel messages"
```

---

### Task 7: Final verification

**Step 1: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 2: Run lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 3: Build frontend**

Run: `cd web/frontend && npm run build`
Expected: Clean build

**Step 4: Trigger resync to backfill existing messages**

After restarting the collector, existing messages will get `text_html` populated on the next resync cycle (startup or signal-triggered). Trigger manually:

```bash
touch /tmp/tematch_resync_signal
```

**Step 5: Verify in web UI**

Open channel messages page — messages with formatting should show bold, italic, links, etc.
