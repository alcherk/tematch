# Tematch — Architecture Design

Smart Telegram bot that checks user subscriptions and recommends personalized messages.

## Requirements

- **Source of subscriptions**: manual input (@channel) + forwarded messages
- **Reading channels**: Telethon (userbot)
- **Recommendations**: Embeddings pre-filter + LLM ranking
- **Storage**: PostgreSQL + pgvector
- **Delivery**: scheduled digest + on-demand (/digest)
- **Scale**: personal project, few users
- **LLM**: abstraction over provider (Claude, OpenAI, etc.)

## Architecture: Two Processes (Approach B)

Collector (Telethon) and Bot (aiogram) run as separate processes.
PostgreSQL serves as the shared state and communication layer.

```
Tematch/
├── collector/                # Process 1: Telethon userbot
│   ├── __init__.py
│   ├── main.py               # Entry point, Telethon client
│   ├── handlers.py           # Handle new messages from channels
│   └── channel_manager.py    # Subscribe/unsubscribe channels
│
├── bot/                      # Process 2: aiogram Telegram bot
│   ├── __init__.py
│   ├── main.py               # Entry point, aiogram dispatcher
│   ├── handlers/
│   │   ├── start.py          # /start, onboarding
│   │   ├── channels.py       # Add channels (input + forward)
│   │   ├── digest.py         # /digest — manual recommendation request
│   │   └── settings.py       # Schedule, interests configuration
│   └── keyboards.py          # Inline keyboards
│
├── core/                     # Shared code
│   ├── __init__.py
│   ├── config.py             # Pydantic Settings, .env
│   ├── db.py                 # SQLAlchemy async engine + session
│   ├── models.py             # ORM models
│   ├── llm/
│   │   ├── base.py           # Abstract LLM provider
│   │   ├── claude.py         # Claude implementation
│   │   └── openai.py         # OpenAI implementation
│   ├── embeddings.py         # Embedding generation (abstraction)
│   └── recommender.py        # embeddings → pre-filter → LLM rank
│
├── scheduler/                # APScheduler — cron for digests
│   ├── __init__.py
│   └── jobs.py               # Jobs: send digests
│
├── alembic/                  # DB migrations
│   └── versions/
├── alembic.ini
├── docker-compose.yml        # PostgreSQL + collector + bot
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md
```

## Data Model

```sql
-- Users table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    interests TEXT,                    -- Natural language description
    digest_cron VARCHAR(50) DEFAULT '0 9 * * *',
    created_at TIMESTAMP DEFAULT NOW()
);

-- Channels table
CREATE TABLE channels (
    id SERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username VARCHAR(255),
    title VARCHAR(255),
    last_fetched_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- User-Channel subscriptions
CREATE TABLE user_channels (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    channel_id INTEGER REFERENCES channels(id),
    added_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, channel_id)
);

-- Messages with embeddings
CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    channel_id INTEGER REFERENCES channels(id),
    telegram_msg_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    embedding vector(1536),
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(channel_id, telegram_msg_id)
);

-- Recommendations
CREATE TABLE recommendations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    message_id INTEGER REFERENCES messages(id),
    score FLOAT NOT NULL,
    delivered BOOLEAN DEFAULT FALSE,
    feedback VARCHAR(10),             -- 'like', 'dislike', or NULL
    created_at TIMESTAMP DEFAULT NOW()
);
```

## Data Flow

### Content Collection (collector, continuous)
1. Telethon listens for new messages from user-subscribed channels
2. For each message, generates embedding via LLM provider
3. Saves `(text, embedding, channel_id, date)` to PostgreSQL

### Digest (scheduler or /digest)
1. Get user `interests` + `feedback` history
2. Form query vector from interest profile
3. pgvector: `SELECT ... ORDER BY embedding <=> $query LIMIT 50` — rough selection
4. LLM receives 50 candidates + profile → returns top-5 with scores
5. Bot sends each message with inline buttons (like/dislike)
6. Feedback is stored in `recommendations`, enriching the profile

### Adding a Channel (bot)
1. User forwards a message or types `@channel_name`
2. Bot saves to `user_channels`
3. Collector picks up new channel from DB on next cycle

## Dependencies

```
# Telegram
aiogram>=3.0
telethon>=1.34

# Database
sqlalchemy[asyncio]>=2.0
asyncpg
alembic
pgvector

# LLM
anthropic
openai
tiktoken

# Scheduling
apscheduler>=3.10

# Config & Utils
pydantic-settings
python-dotenv
```

## Docker Compose

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: tematch
      POSTGRES_USER: tematch
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  collector:
    build: .
    command: python -m collector.main
    depends_on: [postgres]
    env_file: .env

  bot:
    build: .
    command: python -m bot.main
    depends_on: [postgres]
    env_file: .env

volumes:
  pgdata:
```

## Error Handling

| Risk | Mitigation |
|------|-----------|
| Telethon flood wait | Exponential backoff + `FloodWaitError` handler |
| LLM API unavailable | Retry with backoff, digest postponed, user notified |
| Channel became private/deleted | Collector marks channel as `inactive` |
| Embedding dimension changed (provider switch) | Versioning in `messages`, re-embed on migration |
| Too many messages per day (tokens) | Candidate limit for LLM, `tiktoken` for control |

## Configuration (.env)

```
TG_API_ID=...
TG_API_HASH=...
TG_BOT_TOKEN=...
TG_SESSION_NAME=tematch_collector
DATABASE_URL=postgresql+asyncpg://tematch:pass@localhost:5432/tematch
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
CANDIDATES_LIMIT=50
DIGEST_SIZE=5
DEFAULT_DIGEST_CRON=0 9 * * *
```
