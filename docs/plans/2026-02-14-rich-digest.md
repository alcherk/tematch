# Rich Formatted Digest — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redesign Telegram digest messages for better visual hierarchy and scannability using structured card layout with expandable blockquotes.

**Architecture:** Rewrite `_format_single_item` in `bot/formatters.py` to produce a card-style layout: bold header with percentage score, source link, body in expandable `<blockquote>` when >150 chars, thread counts instead of inline snippets. Update divider in `format_digest_page`. Bump `MAX_BODY_LEN` to 800.

**Tech Stack:** Python 3.9, aiogram 3 (HTML parse mode), Telegram Bot API HTML

---

### Task 1: Update constants and write failing tests for new format

**Files:**
- Modify: `bot/formatters.py:13` (MAX_BODY_LEN)
- Modify: `tests/test_formatters.py`

**Step 1: Write failing tests**

Add these tests to the END of `tests/test_formatters.py`:

```python
# --- Rich digest format ---


def test_rich_digest_header_format():
    """Header should have emoji, bold channel, percentage score."""
    items = [_make_digest_item(index=1, score=0.8523, title="TestChan")]
    result = format_digest_page(items)
    assert "📌 1" in result
    assert "<b>TestChan</b>" in result
    assert "⭐ 85%" in result
    # Old decimal format should NOT appear
    assert "0.85" not in result


def test_rich_digest_divider():
    """Divider between items should use box-drawing character."""
    items = [
        _make_digest_item(index=1, rec_id=100),
        _make_digest_item(index=2, rec_id=101),
    ]
    result = format_digest_page(items)
    assert "━" in result
    # Old divider should NOT appear
    assert "———" not in result


def test_rich_digest_short_body_inline():
    """Body <=150 chars should be inline (no blockquote)."""
    items = [_make_digest_item(text="Short message body here")]
    result = format_digest_page(items)
    assert "Short message body here" in result
    assert "<blockquote" not in result


def test_rich_digest_long_body_expandable():
    """Body >150 chars should be in expandable blockquote."""
    long_text = "A" * 200
    items = [_make_digest_item(text=long_text)]
    result = format_digest_page(items)
    assert "<blockquote expandable>" in result
    assert "</blockquote>" in result


def test_rich_digest_thread_counts():
    """Thread should show counts, not inline snippets."""
    thread = {
        "parents": [_make_msg(text="Parent 1"), _make_msg(text="Parent 2")],
        "children": [_make_msg(text="Child reply")],
    }
    items = [_make_digest_item(thread=thread)]
    result = format_digest_page(items)
    # Should have count summary
    assert "↩️ 2" in result
    assert "💬 1" in result
    # Should NOT have inline parent/child text
    assert "Parent 1" not in result
    assert "Child reply" not in result


def test_rich_digest_thread_only_parents():
    """Thread with only parents (no children) should only show parent count."""
    thread = {
        "parents": [_make_msg(text="Parent")],
        "children": [],
    }
    items = [_make_digest_item(thread=thread)]
    result = format_digest_page(items)
    assert "↩️ 1" in result
    assert "💬" not in result


def test_rich_digest_thread_only_children():
    """Thread with only children (no parents) should only show child count."""
    thread = {
        "parents": [],
        "children": [_make_msg(text="Reply 1"), _make_msg(text="Reply 2")],
    }
    items = [_make_digest_item(thread=thread)]
    result = format_digest_page(items)
    assert "💬 2" in result
    assert "↩️" not in result


def test_rich_digest_no_thread_no_summary():
    """No thread context = no thread summary line."""
    items = [_make_digest_item(thread=None)]
    result = format_digest_page(items)
    assert "↩️" not in result
    assert "💬" not in result


def test_rich_digest_text_html_in_expandable():
    """text_html should be used inside expandable blockquote."""
    msg = _make_msg_with_html(
        text="A" * 200,
        text_html="<strong>" + "A" * 200 + "</strong>",
    )
    ch = _make_channel(username="chan")
    ch.title = "Test Channel"
    item = DigestItem(index=1, msg=msg, channel=ch, score=0.8, rec_id=100)
    result = format_digest_page([item])
    assert "<blockquote expandable>" in result
    assert "<strong>" in result


def test_rich_digest_max_body_len_800():
    """Body should truncate at 800 chars, not 600."""
    text_700 = "B" * 700
    items = [_make_digest_item(text=text_700)]
    result = format_digest_page(items)
    # 700 chars should NOT be truncated (old limit was 600)
    assert "…" not in result
    assert "B" * 700 in result
```

**Step 2: Run tests to verify they fail**

Run: `venv/bin/python -m pytest tests/test_formatters.py::test_rich_digest_header_format tests/test_formatters.py::test_rich_digest_divider tests/test_formatters.py::test_rich_digest_short_body_inline -x -q`
Expected: FAIL (old format doesn't match new assertions)

**Step 3: Commit tests**

```bash
git add tests/test_formatters.py
git commit -m "test: add failing tests for rich digest format"
```

---

### Task 2: Implement the new `_format_single_item`

**Files:**
- Modify: `bot/formatters.py:13,48-94`

**Step 1: Update MAX_BODY_LEN**

In `bot/formatters.py` line 13, change:
```python
MAX_BODY_LEN = 600
```
to:
```python
MAX_BODY_LEN = 800
```

**Step 2: Add EXPANDABLE_THRESHOLD constant**

After `MAX_PAGE_CHARS` (line 15), add:
```python
EXPANDABLE_THRESHOLD = 150
```

**Step 3: Rewrite `_format_single_item`**

Replace the entire `_format_single_item` function (lines 48-89) with:

```python
def _format_single_item(item: DigestItem) -> str:
    parts: list[str] = []

    # Header: emoji + index + bold channel + percentage score
    score_pct = round(item.score * 100)
    header = f"📌 {item.index} · <b>{html_escape(item.channel.title or '')}</b> · ⭐ {score_pct}%"
    parts.append(header)

    # Link (with media indicator)
    link = generate_message_link(item.channel, item.msg.telegram_msg_id)
    if link:
        has_media = getattr(item.msg, "has_media", False)
        link_text = f'<a href="{link}">🔗 Источник</a>'
        if has_media:
            link_text += " 🖼"
        parts.append(link_text)

    # Body — use text_html when available, expandable when long
    body_html = getattr(item.msg, "text_html", None)
    if body_html:
        body = _truncate(body_html, MAX_BODY_LEN)
    else:
        body = html_escape(_truncate(item.msg.text, MAX_BODY_LEN))

    if len(item.msg.text) > EXPANDABLE_THRESHOLD:
        parts.append(f"<blockquote expandable>{body}</blockquote>")
    else:
        parts.append(body)

    # Thread summary — counts only, no inline snippets
    if item.thread:
        parent_count = len(item.thread.get("parents", []))
        child_count = len(item.thread.get("children", []))
        thread_parts: list[str] = []
        if parent_count:
            thread_parts.append(f"↩️ {parent_count} контекстных")
        if child_count:
            thread_parts.append(f"💬 {child_count} ответ.")
        if thread_parts:
            parts.append(" · ".join(thread_parts))

    return "\n".join(parts)
```

**Step 4: Update divider in `format_digest_page`**

Replace line 94:
```python
    return "\n\n———\n\n".join(sections)
```
with:
```python
    return "\n\n━━━━━━━━━━━━━━━━━━━\n\n".join(sections)
```

**Step 5: Update divider in `split_digest_pages`**

In `split_digest_pages`, line 105, update the divider length calculation:
```python
        divider_len = len("\n\n━━━━━━━━━━━━━━━━━━━\n\n") if current_page else 0
```

**Step 6: Run all formatter tests**

Run: `venv/bin/python -m pytest tests/test_formatters.py -x -q -W error`
Expected: All pass (new + existing)

Note: Some existing tests check for old format (`"———"`, `"0.85"`, `"<b>1.</b>"`). These will need updating — see Task 3.

---

### Task 3: Fix broken existing tests

**Files:**
- Modify: `tests/test_formatters.py`

The following existing tests will break because the format changed. Update them:

**`test_format_digest_page_basic`** — change:
- `assert "<b>1.</b>" in result` → `assert "📌 1" in result`
- `assert "<b>2.</b>" in result` → `assert "📌 2" in result`
- `assert "0.85" in result` → `assert "85%" in result`

**`test_format_digest_page_html_tags`** — keep `assert "<b>" in result` (still true, used in channel title)

**`test_format_digest_page_escapes_user_content`** — the text `"Use <b>tag</b> & more"` is 24 chars (≤150), so it stays inline. Assertions `assert "&lt;b&gt;" in result` and `assert "&amp;" in result` should still pass.

**`test_format_digest_page_with_link`** — keep as-is (link format unchanged)

**`test_format_digest_page_media_indicator`** — keep `assert "🖼" in result`

**`test_format_digest_page_no_media_indicator`** — keep as-is

**`test_format_digest_page_no_link`** — keep as-is

**`test_format_digest_page_with_thread_parents`** — old test checks `"Parent context" in result`. New format shows counts instead. Update:
```python
def test_format_digest_page_with_thread_parents():
    thread = {"parents": [_make_msg(text="Parent context")], "children": []}
    items = [_make_digest_item(thread=thread)]
    result = format_digest_page(items)
    assert "↩️ 1" in result
```

**`test_format_digest_page_with_thread_children`** — same pattern:
```python
def test_format_digest_page_with_thread_children():
    thread = {"parents": [], "children": [_make_msg(text="Child reply")]}
    items = [_make_digest_item(thread=thread)]
    result = format_digest_page(items)
    assert "💬 1" in result
```

**`test_format_digest_page_divider_between_items`** — change:
- `assert "———" in result` → `assert "━" in result`

**`test_format_digest_page_truncates_long_body`** — body of 1000 chars will be in expandable blockquote, truncated at 800. Update:
- `assert "X" * 601 not in result` → `assert "X" * 801 not in result`

**Step 1: Apply all fixes above**

**Step 2: Run all formatter tests**

Run: `venv/bin/python -m pytest tests/test_formatters.py -x -q -W error`
Expected: All pass

**Step 3: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 4: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 5: Commit**

```bash
git add bot/formatters.py tests/test_formatters.py
git commit -m "feat(digest): rich card layout with expandable blockquotes"
```

---

### Task 4: Verification

**Step 1: Run full test suite**

Run: `venv/bin/python -m pytest tests/ -x -q -W error`
Expected: All pass

**Step 2: Lint**

Run: `venv/bin/ruff check .`
Expected: Clean

**Step 3: Manual test**

Reset last_digest_at and request a digest:
```sql
docker exec tematch-postgres-1 psql -U tematch -d tematch -c "UPDATE users SET last_digest_at = NULL WHERE telegram_id = 177363488;"
```
Then send `/digest` in Telegram. Verify:
- Header has `📌 N · <b>Channel</b> · ⭐ XX%`
- Long messages are in expandable blockquotes
- Short messages are inline
- Divider is `━━━━━━━━━━━━━━━━━━━`
- Thread shows counts (not inline snippets)
- Original formatting (bold, quotes) preserved in body
