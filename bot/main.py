import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.types import TelegramObject

from bot.handlers import channels, digest, settings, start
from core.config import Settings
from core.db import create_engine, create_session_factory
from core.embeddings import EmbeddingService
from core.llm import create_llm_provider
from core.recommender import Recommender

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    app_settings = Settings()

    engine = create_engine(app_settings)
    session_factory = create_session_factory(engine)

    llm_provider = create_llm_provider(
        provider=app_settings.LLM_PROVIDER,
        api_key=(
            app_settings.ANTHROPIC_API_KEY
            if app_settings.LLM_PROVIDER == "claude"
            else app_settings.OPENAI_API_KEY
        ),
        model=app_settings.LLM_MODEL,
    )
    embedding_service = EmbeddingService(
        api_key=app_settings.OPENAI_API_KEY,
        model=app_settings.EMBEDDING_MODEL,
        dim=app_settings.EMBEDDING_DIM,
    )
    recommender = Recommender(
        embedding_service=embedding_service,
        llm_provider=llm_provider,
        candidates_limit=app_settings.CANDIDATES_LIMIT,
        digest_size=app_settings.DIGEST_SIZE,
    )

    bot = Bot(token=app_settings.TG_BOT_TOKEN)
    dp = Dispatcher()

    @dp.update.outer_middleware()
    async def db_middleware(handler, event: TelegramObject, data: dict):
        async with session_factory() as session:
            data["session"] = session
            data["recommender"] = recommender
            data["embedding_service"] = embedding_service
            return await handler(event, data)

    dp.include_router(start.router)
    dp.include_router(channels.router)
    dp.include_router(digest.router)
    dp.include_router(settings.router)

    logger.info("Bot started.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
