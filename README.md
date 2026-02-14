# Tematch

Smart Telegram bot that curates personalized content from your channel subscriptions.

Subscribe to channels, describe your interests, and get a daily digest of the most relevant posts — ranked by AI.

## How it works

1. **Subscribe** — forward a channel post or send `@channel_name`
2. **Set interests** — `/interests ML, crypto, космос`
3. **Get digest** — `/digest` returns top-5 personalized recommendations

Under the hood: pgvector similarity pre-filters top 50 candidates, then an LLM ranks the best 5.

## Architecture

```
┌──────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  Telegram    │────▶│  Collector (Telethon) │────▶│              │
│  Channels    │     │  live + resync        │     │  PostgreSQL  │
└──────────────┘     └──────────────────────┘     │  + pgvector  │
                                                   │              │
┌──────────────┐     ┌──────────────────────┐     │  messages    │
│  User        │◀───▶│  Bot (aiogram)       │◀───▶│  embeddings  │
│  in Telegram │     │  commands + digest    │     │  users       │
└──────────────┘     └──────────────────────┘     └──────────────┘
```

Two independent processes share only the database:
- **Collector** — Telethon userbot captures channel messages, embeds them on ingest
- **Bot** — aiogram handles commands, runs the recommendation pipeline

## Tech stack

- Python 3.9+, aiogram 3, Telethon
- PostgreSQL + pgvector
- SQLAlchemy 2 async + Alembic
- OpenAI / Claude (swappable via config)

## Bot commands

| Command | Description |
|---------|-------------|
| `/start` | Create user profile |
| `/digest` | Get personalized recommendations |
| `/interests <text>` | Set interests in natural language |
| `/schedule <cron>` | Set auto-digest schedule |
| `/schedule off` | Disable auto-digest |

## Quick start

See [docs/quick-start-guide.md](docs/quick-start-guide.md) for full setup instructions.

**TL;DR:**

```bash
cp .env.example .env   # fill in TG_API_ID, TG_API_HASH, TG_BOT_TOKEN, OPENAI_API_KEY
docker compose up -d postgres
venv/bin/alembic upgrade head
venv/bin/python -m bot.main        # terminal 1
venv/bin/python -m collector.main  # terminal 2
```

## Tests

```bash
# Unit tests (41) — no dependencies
venv/bin/pytest tests/ --ignore=tests/e2e -v

# E2E tests (34) — need Postgres + pgvector
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/e2e/ -v

# All 75
TEST_DATABASE_URL=postgresql+asyncpg://tematch:tematch@localhost:5432/tematch_test \
  venv/bin/pytest tests/ -v
```

## License

Private project.
