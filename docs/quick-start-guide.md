# Tematch — Quick Start Guide

## Prerequisites

| What | Why |
|------|-----|
| Docker | For Postgres + pgvector |
| Telegram API credentials | `TG_API_ID` + `TG_API_HASH` from [my.telegram.org](https://my.telegram.org) |
| Bot token | From [@BotFather](https://t.me/BotFather) |
| OpenAI API key | For embeddings + LLM ranking |

---

## Option A: Docker Compose (full stack)

```bash
# 1. Configure
cp .env.example .env
# Edit .env — fill in:
#   TG_API_ID, TG_API_HASH  — from https://my.telegram.org
#   TG_BOT_TOKEN             — from @BotFather
#   OPENAI_API_KEY           — from OpenAI dashboard

# 2. Start everything
docker compose up -d
```

This starts 3 services: `postgres` (pgvector), `bot` (aiogram), `collector` (Telethon).

**Note:** The collector uses Telethon (user-session auth). First run requires interactive login:

```bash
docker compose up -d postgres
docker compose run --rm collector   # interactive — enter phone/code
# After auth succeeds, Ctrl+C, then:
docker compose up -d
```

---

## Option B: Local venv (for development)

```bash
# 1. Configure
cp .env.example .env
# Edit .env — same as above

# 2. Start Postgres only
docker compose up -d postgres

# 3. Run Alembic migrations (once DB is healthy)
venv/bin/alembic upgrade head

# 4. Terminal 1 — bot
venv/bin/python -m bot.main

# 5. Terminal 2 — collector
venv/bin/python -m collector.main
```

---

## Quick check it works

After the bot starts, in Telegram:

```
/start                              # creates user
@durov                              # subscribes to channel
/interests ML, космос, инди-игры    # sets interests
/digest                             # generates recommendations
```

---

## Running tests

```bash
# Unit tests (no DB needed)
venv/bin/pytest tests/ --ignore=tests/e2e -v

# E2E tests (need Postgres running)
docker compose up -d postgres
docker exec tematch-postgres-1 psql -U tematch -c "CREATE DATABASE tematch_test;" 2>/dev/null
docker exec tematch-postgres-1 psql -U tematch -d tematch_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/e2e/ -v

# All 75 tests
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/ -v
```

---

## Useful DB queries

```sql
-- Check users
SELECT id, telegram_id, interests, digest_cron, last_digest_at FROM users;

-- Check subscriptions
SELECT u.telegram_id, c.title, c.username
FROM user_channels uc
JOIN users u ON u.id = uc.user_id
JOIN channels c ON c.id = uc.channel_id;

-- Check collected messages
SELECT id, channel_id, telegram_msg_id, LEFT(text, 60), date
FROM messages ORDER BY id DESC LIMIT 10;

-- Check LLM usage for today
SELECT provider, operation, tokens_in, tokens_out, cost_estimate
FROM llm_usage WHERE date = CURRENT_DATE;
```
