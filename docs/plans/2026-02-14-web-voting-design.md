# Web UI Voting — Design

## Goal
Add per-recommendation voting (👍/👎) to both the user dashboard and admin panel in the web UI. Admin sees all users' recommendations; regular users see their own. Re-voting is allowed.

## Backend

### PATCH /api/recommendations/{id}/feedback
- Auth: any authenticated user
- Body: `{"feedback": "like" | "dislike"}`
- Authorization: recommendation must belong to current user, OR user is admin
- Updates `Recommendation.feedback`, commits, returns `{"ok": true, "feedback": "like"}`

### GET /api/admin/recommendations
- Auth: admin-only
- Returns last 100 delivered recommendations across all users
- Fields: id, score, feedback, created_at, text_preview (~100 chars), user_telegram_id, channel_title, message_link (if available)

## Frontend

### Dashboard (digests section)
- Add 👍/👎 buttons next to each recommendation in the existing digests list
- Highlight active vote state (cyan glow for current selection)
- Clicking a button calls PATCH endpoint and updates state optimistically

### Admin panel (new section)
- New "Recommendations" table section below existing admin content
- Columns: user, channel, text preview, score, feedback buttons, timestamp
- Same voting buttons as dashboard — admin can vote on any recommendation

## Files to modify
| File | Change |
|---|---|
| `web/routers/admin.py` | Add GET /admin/recommendations |
| `web/routers/users.py` | Add PATCH /recommendations/{id}/feedback |
| `web/frontend/src/pages/Dashboard.tsx` | Add vote buttons to digests |
| `web/frontend/src/pages/Admin.tsx` | Add recommendations table with voting |
| `web/frontend/src/api.ts` | Add voteFeedback() helper |
