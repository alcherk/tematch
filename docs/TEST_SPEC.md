# Tematch — Test Specification

## Testable Features

1. `/start` registers new user and greets returning user
2. Forward message from channel subscribes user to that channel
3. `@channel_name` subscribes user to channel by username
4. `/interests <text>` saves interests and caches embedding vector
5. `/schedule <cron>` sets digest schedule; `/schedule off` disables it
6. `/digest` returns top-5 recommendations from subscribed channels
7. `/digest` refuses after 3 digests per day (rate limit)
8. `/digest` refuses when daily token budget (500K) exhausted
9. Digest uses time window: since last digest, capped at 72h
10. Recommendations are deduplicated by content hash across channels
11. Feedback buttons (like/dislike) update recommendation record
12. Collector captures live channel messages via Telethon
13. Collector resyncs missed messages on startup (up to 72h)
14. Embedding buffer batches vectorization (20 messages or 30s flush)
15. Cached interests embedding skips API call in recommender
16. LLM usage is logged per call (provider, operation, tokens)

---

## Test Architecture

```
tests/
├── *.py                    # Unit tests (41) — mocked DB/API, run anywhere
└── e2e/
    ├── conftest.py         # Real Postgres + pgvector fixtures
    ├── test_onboarding.py  # Features 1-5: user, channel, interests, schedule
    ├── test_dedup.py       # Feature 10: content-hash dedup
    ├── test_digest_window.py  # Feature 9: hybrid time window
    ├── test_rate_limits.py # Features 7, 8, 16: digest cap, token budget, usage logging
    ├── test_collector.py   # Features 12, 14: message storage, embedding buffer
    ├── test_resync.py      # Feature 13: collector resync offset
    └── test_recommender.py # Features 10, 15: dedup + embedding cache
```

**Unit tests** — no dependencies, mock everything, fast:
```bash
venv/bin/pytest tests/ --ignore=tests/e2e -v
```

**E2E tests** — need Postgres + pgvector running:
```bash
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/e2e/ -v
```

**All tests together:**
```bash
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/ -v
```

---

## E2E Prerequisites

```bash
# Start Postgres with pgvector
docker compose up -d postgres

# Create test database (once)
docker exec tematch-postgres-1 \
  psql -U tematch -c "CREATE DATABASE tematch_test;"
docker exec tematch-postgres-1 \
  psql -U tematch -d tematch_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

The `tests/e2e/conftest.py` handles table creation/teardown automatically via
`Base.metadata.create_all` / `drop_all`. Each test gets a rolled-back session.

### CI One-Liner

```bash
docker compose up -d postgres && sleep 3 && \
  docker exec tematch-postgres-1 psql -U tematch -c "CREATE DATABASE IF NOT EXISTS tematch_test;" 2>/dev/null; \
  docker exec tematch-postgres-1 psql -U tematch -d tematch_test -c "CREATE EXTENSION IF NOT EXISTS vector;" && \
  TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/ -v
```

---

## Manual Testing

### Setup

```bash
cp .env.example .env
# Fill in: TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, OPENAI_API_KEY

docker compose up -d postgres
venv/bin/alembic upgrade head
```

Start in two terminals:
```bash
# Terminal 1: bot
venv/bin/python -m bot.main

# Terminal 2: collector
venv/bin/python -m collector.main
```

### Test Scenarios

| # | Feature | Steps | Expected |
|---|---------|-------|----------|
| 1 | `/start` (new) | Send `/start` to bot | Welcome with 3 steps: add channel, set interests, get digest |
| 1 | `/start` (return) | Send `/start` again | "С возвращением!" |
| 2 | Forward subscribe | Forward any channel post to bot | "Канал «...» добавлен!" |
| 3 | @username subscribe | Send `@durov` | "Канал @durov добавлен!" |
| 4 | Set interests | `/interests ML, crypto, космос` | "Интересы обновлены: ML, crypto, космос" |
| 5 | Set schedule | `/schedule 0 9 * * *` | "Расписание обновлено: 0 9 * * *" |
| 5 | Disable schedule | `/schedule off` | "Автодайджест отключён." |
| 6 | Digest | `/digest` (after doing 2 + 4) | Messages with scores + 👍/👎 buttons |
| 7 | Digest rate limit | Send `/digest` 4× in a row | 4th time: "Лимит дайджестов на сегодня: 3/3" |
| 8 | Token budget | Set `DAILY_TOKEN_BUDGET=1` in .env, restart bot, `/digest` | "Дневной лимит токенов исчерпан." |
| 9 | Time window | `/digest` twice; check second has only new content | Second digest skips already-seen period |
| 10 | Dedup | Subscribe to 2 channels that repost same content, `/digest` | Each post appears once |
| 11 | Feedback | Tap 👍 or 👎 on recommendation | "Спасибо за отзыв!" |
| 12 | Live collection | Post in subscribed channel while collector runs | `SELECT * FROM messages ORDER BY id DESC LIMIT 5;` shows it |
| 13 | Resync | Stop collector → post in channel → restart collector | Missed messages appear in DB |
| 14 | Batch embeddings | Post 20+ messages rapidly, watch collector logs | "Flushed 20 embeddings" in logs |
| 15 | Cached embedding | Set interests, `/digest`, check logs | No `embed_text` call logged for interests |
| 16 | LLM usage | After `/digest`, check DB | `SELECT * FROM llm_usage WHERE date = CURRENT_DATE;` |

### DB Queries for Verification

```sql
-- Check users
SELECT id, telegram_id, interests, digest_cron, last_digest_at FROM users;

-- Check subscriptions
SELECT u.telegram_id, c.title, c.username
FROM user_channels uc
JOIN users u ON u.id = uc.user_id
JOIN channels c ON c.id = uc.channel_id;

-- Check collected messages
SELECT id, channel_id, telegram_msg_id, LEFT(text, 60), content_hash, date
FROM messages ORDER BY id DESC LIMIT 10;

-- Check recommendations and feedback
SELECT r.id, r.score, r.delivered, r.feedback, LEFT(m.text, 60)
FROM recommendations r
JOIN messages m ON m.id = r.message_id
ORDER BY r.id DESC LIMIT 10;

-- Check LLM usage for today
SELECT provider, operation, tokens_in, tokens_out, cost_estimate
FROM llm_usage WHERE date = CURRENT_DATE;

-- Check digest count for a user
SELECT COUNT(DISTINCT date_trunc('minute', created_at))
FROM recommendations
WHERE user_id = 1 AND delivered = true
AND created_at >= CURRENT_DATE;
```

---

## Feature ↔ Test Mapping

| Feature | Unit Tests | E2E Tests |
|---------|-----------|-----------|
| 1. /start | `test_bot_handlers` | `e2e/test_onboarding::test_new_user_*`, `test_returning_*` |
| 2. Forward subscribe | — | `e2e/test_onboarding::test_channel_subscription_via_forward` |
| 3. @username subscribe | — | `e2e/test_onboarding::test_channel_subscription_via_username` |
| 4. /interests | — | `e2e/test_onboarding::test_interests_saved` |
| 5. /schedule | `test_scheduler` | `e2e/test_onboarding::test_schedule_saved_and_cleared` |
| 6. /digest | `test_recommender` | — (requires full stack) |
| 7. Digest rate limit | `test_llm_limits` | `e2e/test_rate_limits::test_digest_count_*` |
| 8. Token budget | `test_llm_usage` | `e2e/test_rate_limits::test_token_budget_*` |
| 9. Time window | `test_digest_window` | `e2e/test_digest_window::*` |
| 10. Dedup | `test_dedup` | `e2e/test_dedup::*`, `e2e/test_recommender::test_dedup_*` |
| 11. Feedback | `test_bot_handlers` | — (requires Telegram callback) |
| 12. Collector | `test_collector` | `e2e/test_collector::test_message_stored_*`, `test_duplicate_*` |
| 13. Resync | `test_resync` | `e2e/test_resync::*` |
| 14. Embedding buffer | `test_embedding_buffer` | `e2e/test_collector::test_embedding_buffer_*` |
| 15. Cached embedding | `test_interests_cache` | `e2e/test_recommender::test_cached_*`, `test_no_cached_*` |
| 16. LLM usage logging | `test_llm_usage` | `e2e/test_rate_limits::test_log_usage_*` |
