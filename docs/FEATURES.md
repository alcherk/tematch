# Tematch — Key Features

Smart Telegram bot that curates personalized content from your channel subscriptions.

## Core Features

### 1. Channel Management
- **Forward to add** — forward any message from a channel to the bot, it auto-detects the source and subscribes
- **Manual add** — send `@channel_name` to subscribe
- **List & remove** — view all tracked channels, unsubscribe with one tap

### 2. Smart Recommendations
- **Two-stage pipeline** — fast vector similarity pre-filter (pgvector, top 50), then LLM precision ranking (top 5)
- **Personal interest profile** — describe your interests in natural language, the bot uses it for matching
- **Feedback loop** — like/dislike buttons on each recommendation improve future suggestions

### 3. Digest Delivery
- **On-demand** — `/digest` command returns personalized picks instantly
- **Scheduled** — automated digest via cron schedule (e.g., every morning at 9:00)
- **Configurable** — `/schedule 0 9 * * *` or `/schedule off`

### 4. Content Collection
- **Real-time** — Telethon userbot listens for new messages as they're posted
- **Embedding on ingest** — every message is vectorized immediately for fast similarity search
- **Resilient** — collector and bot run independently; if one restarts, the other continues

### 5. LLM Abstraction
- **Swappable providers** — Claude, OpenAI, or any future provider via a single config change
- **Cost control** — embeddings for bulk filtering (cheap), LLM only for final ranking of small batches

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Onboarding, create user profile |
| `/digest` | Get personalized recommendations now |
| `/interests <text>` | Set interest profile in natural language |
| `/schedule <cron>` | Set automated digest schedule |
| `/schedule off` | Disable automated digests |

## Architecture Highlights

- **Two-process design** — collector (Telethon) and bot (aiogram) share nothing except PostgreSQL
- **PostgreSQL + pgvector** — single database for relational data and vector search
- **Docker Compose** — one command to run the entire stack
