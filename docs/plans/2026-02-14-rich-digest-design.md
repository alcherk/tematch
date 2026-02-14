# Rich Formatted Digest — Design

## Overview
Redesign Telegram digest messages for better visual hierarchy and scannability. Current format is plain and hard to scan; new format uses structured "card" layout with expandable blockquotes.

## Single Item Format

```
📌 1 · <b>ASupersharij</b> · ⭐ 85%
<a href="https://t.me/...">🔗 Источник</a> 🖼

<blockquote expandable>Full message body with original
formatting preserved (bold, italic, quotes)...</blockquote>

↩️ 2 контекстных · 💬 1 ответ
```

## Rules

**Header:** `📌 {index} · <b>{channel}</b> · ⭐ {score}%`
- Score as integer percentage (85%) instead of decimal (0.85)

**Link:** `<a href="...">🔗 Источник</a>` + `🖼` when has_media

**Body:**
- Uses `text_html` when available (preserves original Telegram formatting)
- Falls back to `html_escape(text)` when `text_html` is NULL
- When body >150 chars → wrap in `<blockquote expandable>` (collapsed by default, tap to expand)
- When body ≤150 chars → plain inline (no blockquote wrapper)
- Max body length: 800 chars (up from 600)

**Thread summary:** Single count line instead of inline snippets
- `↩️ N контекстных · 💬 M ответ(ов)` — only shown when thread exists
- No inline parent/child text snippets (cleaner; user taps source link for context)

**Divider:** `━━━━━━━━━━━━━━━━━━━` (unicode box-drawing) between items

## Scope
- Only `bot/formatters.py` changes
- `_format_single_item` — new card layout
- `format_digest_page` — new divider
- `MAX_BODY_LEN` — 600 → 800
- `format_recommendation` unchanged
- No model/migration/frontend changes
