from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.embeddings import EmbeddingService
from core.llm.base import LLMProvider
from core.models import Message


class Recommender:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        llm_provider: LLMProvider,
        candidates_limit: int = 50,
        digest_size: int = 5,
    ):
        self.embedding_service = embedding_service
        self.llm_provider = llm_provider
        self.candidates_limit = candidates_limit
        self.digest_size = digest_size

    async def recommend(
        self,
        session: AsyncSession,
        user_id: int,
        interests: str,
        channel_ids: list[int],
    ) -> list[dict]:
        # Stage 1: pgvector similarity search
        query_vector = await self.embedding_service.embed_text(interests)

        stmt = (
            select(Message)
            .where(Message.channel_id.in_(channel_ids))
            .where(Message.embedding.isnot(None))
            .order_by(Message.embedding.cosine_distance(query_vector))
            .limit(self.candidates_limit)
        )
        result = await session.execute(stmt)
        candidates = result.scalars().all()

        if not candidates:
            return []

        # Stage 2: LLM ranking
        messages_for_llm = [{"id": m.id, "text": m.text} for m in candidates]
        ranked = await self.llm_provider.rank_messages(
            messages=messages_for_llm,
            user_interests=interests,
            limit=self.digest_size,
        )

        return ranked
