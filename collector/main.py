import asyncio
import logging

from telethon import TelegramClient, events

from collector.channel_manager import get_active_channel_ids
from collector.handlers import handle_new_message
from core.config import Settings
from core.db import create_engine, create_session_factory
from core.embeddings import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    settings = Settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    embedding_service = EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dim=settings.EMBEDDING_DIM,
    )

    client = TelegramClient(
        settings.TG_SESSION_NAME,
        settings.TG_API_ID,
        settings.TG_API_HASH,
    )

    @client.on(events.NewMessage)
    async def on_new_message(event):
        if not event.is_channel:
            return

        chat = await event.get_chat()

        async with session_factory() as session:
            active_ids = await get_active_channel_ids(session)
            if chat.id not in active_ids:
                return

            await handle_new_message(
                session=session,
                embedding_service=embedding_service,
                channel_telegram_id=chat.id,
                message_id=event.id,
                text=event.raw_text,
                date=event.date,
            )

    await client.start()
    logger.info("Collector started. Listening for channel messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
