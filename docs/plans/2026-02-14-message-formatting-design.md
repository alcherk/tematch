# Message Formatting Preservation — Design

## Overview
Preserve original Telegram message formatting (bold, italic, code, links, quotes, underline, strikethrough) throughout the pipeline: collector stores HTML, digest and web render it.

## Approach
Add `text_html` column to `Message` model. Collector converts Telethon entities to HTML via `telethon.extensions.html.unparse()`. Plain `text` stays for embeddings, content hash, and LLM ranking. Re-collection updates existing messages that lack `text_html`.

## Storage
- New column: `Message.text_html` (Text, nullable)
- Alembic migration to add the column
- `text` remains unchanged (plain text for ML pipeline)

## Collector
- `handle_new_message` accepts optional `entities` parameter
- Converts to HTML: `telethon.extensions.html.unparse(text, entities)` when entities present
- Stores result in `text_html`
- When message already exists but `text_html` is NULL, updates it (backfill on resync)
- Live handler passes `event.text` + `event.entities`
- Resync passes `msg.text` + `msg.entities`

## Digest Formatter
- `_format_single_item` uses `msg.text_html` when available (already HTML)
- Falls back to `html_escape(msg.text)` when `text_html` is NULL
- Thread snippets (parents/children) also use `text_html` when available

## Web UI
- API response includes `text_html` field
- `ChannelMessages.tsx` renders HTML content (generated server-side from Telethon entities, not user input — safe by construction)
- Falls back to plain text when `text_html` is NULL

## Supported Formatting
All Telegram entity types: bold, italic, underline, strikethrough, code, pre, links, mentions, blockquotes, spoilers.
