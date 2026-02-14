import asyncio
import logging

from telethon import TelegramClient, events

from collector.channel_manager import get_active_channel_ids
from collector.embedding_buffer import EmbeddingBuffer
from collector.handlers import handle_new_message
from collector.resync import resync_channels
from core.config import Settings
from core.db import create_engine, create_session_factory
from core.embeddings import EmbeddingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_background_tasks: set = set()


async def main():
    settings = Settings()
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)

    embedding_service = EmbeddingService(
        api_key=settings.OPENAI_API_KEY,
        model=settings.EMBEDDING_MODEL,
        dim=settings.EMBEDDING_DIM,
    )

    embedding_buffer = EmbeddingBuffer(
        embedding_service=embedding_service,
        session_factory=session_factory,
        batch_size=settings.EMBEDDING_BATCH_SIZE,
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

            reply_to_msg_id = None
            if event.reply_to and hasattr(event.reply_to, "reply_to_msg_id"):
                reply_to_msg_id = event.reply_to.reply_to_msg_id

            await handle_new_message(
                session=session,
                channel_telegram_id=chat.id,
                message_id=event.id,
                text=event.raw_text,
                date=event.date,
                embedding_buffer=embedding_buffer,
                reply_to_msg_id=reply_to_msg_id,
                has_media=event.media is not None,
            )

        if embedding_buffer.should_flush:
            await embedding_buffer.flush()

    # Periodic flush task
    async def periodic_flush():
        while True:
            await asyncio.sleep(settings.EMBEDDING_FLUSH_INTERVAL)
            await embedding_buffer.flush()

    await client.start()

    # Catch up on missed messages
    logger.info("Starting resync...")
    await resync_channels(
        client=client,
        session_factory=session_factory,
        embedding_buffer=embedding_buffer,
        max_hours=settings.RESYNC_MAX_HOURS,
        batch_size=settings.RESYNC_BATCH_SIZE,
    )
    logger.info("Resync complete. Listening for live messages...")

    task = asyncio.create_task(periodic_flush())
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    logger.info("Collector started. Listening for channel messages...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
