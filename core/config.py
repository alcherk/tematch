from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Telegram
    TG_API_ID: int
    TG_API_HASH: str
    TG_BOT_TOKEN: str
    TG_SESSION_NAME: str = "tematch_collector"

    # Database
    DATABASE_URL: str

    # LLM
    LLM_PROVIDER: str = "openai"
    ANTHROPIC_API_KEY: str = ""
    OPENAI_API_KEY: str = ""

    # Recommender
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIM: int = 1536
    CANDIDATES_LIMIT: int = 50
    DIGEST_SIZE: int = 5

    # Scheduler
    DEFAULT_DIGEST_CRON: str = "0 9 * * *"

    # Hardening
    DIGEST_WINDOW_MAX_HOURS: int = 72
    MAX_DIGESTS_PER_DAY: int = 3
    DAILY_TOKEN_BUDGET: int = 500_000
    EMBEDDING_BATCH_SIZE: int = 20
    EMBEDDING_FLUSH_INTERVAL: int = 30
    RESYNC_MAX_HOURS: int = 72
    RESYNC_BATCH_SIZE: int = 100

    model_config = {"env_file": ".env", "extra": "ignore"}
