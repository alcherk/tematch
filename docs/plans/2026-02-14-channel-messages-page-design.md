# Channel Messages Page — Design

## Overview
Users can tap a subscribed channel in the web dashboard to view all its messages in a paginated table with relevance scores.

## Backend

**Endpoint**: `GET /api/users/me/channels/{channel_id}/messages`

**File**: `web/routers/channels.py`

**Query params**:
- `page` (int, default 1)
- `per_page` (int, default 50)

**Auth**: Verifies user is subscribed to the channel via `UserChannel` join.

**Response**:
```json
{
  "channel": { "id": 6, "title": "...", "username": "..." },
  "messages": [
    {
      "id": 123,
      "text": "...",
      "date": "2026-02-14T03:32:31",
      "has_embedding": true,
      "relevance": 0.72,
      "has_media": false
    }
  ],
  "total": 78,
  "page": 1,
  "per_page": 50
}
```

**Relevance score**: Computed as `1 - cosine_distance(message.embedding, user.interests_embedding)`. Only computed when both embeddings exist; otherwise `null`.

**Sort**: `ORDER BY date DESC` (newest first).

## Frontend

**Route**: `/channels/:id` (added to `App.tsx`)

**New page**: `pages/ChannelMessages.tsx`
- Fetches messages from the API endpoint
- Renders a `cyber-table` with columns: Text (truncated ~200 chars), Date, Embedding (status dot), Relevance (0–100%), Media (icon)
- Prev/Next pagination buttons with page counter
- Back link to dashboard
- Matches existing cyberpunk theme

**ChannelList change**: Channel title in the table becomes a clickable `<Link to={/channels/${ch.id}}>`.

## Table Columns

| Column | Source | Display |
|---|---|---|
| Text | `message.text` | Truncated to ~200 chars |
| Date | `message.date` | Localized datetime |
| Embedding | `embedding IS NOT NULL` | Green/red status dot |
| Relevance | `1 - cosine_distance` | Percentage (0–100%) |
| Media | `message.has_media` | Icon indicator |
