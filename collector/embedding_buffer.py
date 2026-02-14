from __future__ import annotations

import logging

from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker

from core.embeddings import EmbeddingService
from core.llm_usage import log_usage
from core.models import Message

logger = logging.getLogger(__name__)


class EmbeddingBuffer:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        session_factory: async_sessionmaker,
        batch_size: int = 20,
    ):
        self.embedding_service = embedding_service
        self.session_factory = session_factory
        self.batch_size = batch_size
        self._pending: list[tuple[int, str]] = []

    def add(self, message_id: int, text: str) -> None:
        self._pending.append((message_id, text))

    @property
    def should_flush(self) -> bool:
        return len(self._pending) >= self.batch_size

    async def flush(self) -> None:
        if not self._pending:
            return

        batch = self._pending[:]
        self._pending.clear()

        msg_ids = [b[0] for b in batch]
        texts = [b[1] for b in batch]

        try:
            result = await self.embedding_service.embed_texts(texts)
            embeddings = result.embeddings
        except Exception:
            logger.exception("Batch embedding failed for %d messages", len(batch))
            return

        async with self.session_factory() as session:
            for msg_id, embedding in zip(msg_ids, embeddings):
                stmt = (
                    update(Message)
                    .where(Message.id == msg_id)
                    .values(embedding=embedding)
                )
                await session.execute(stmt)
            await log_usage(
                session,
                provider="openai",
                operation="embedding",
                tokens_in=result.tokens,
                tokens_out=0,
            )

        logger.info("Flushed %d embeddings", len(batch))
