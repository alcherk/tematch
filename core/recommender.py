from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.embeddings import EmbeddingService
from core.llm.base import LLMProvider
from core.models import Message


def deduplicate_candidates(candidates: list) -> list:
    seen: dict[str, object] = {}
    for msg in candidates:
        h = msg.content_hash
        if h is None:
            seen[f"_nohash_{msg.id}"] = msg
        elif h not in seen or msg.date < seen[h].date:
            seen[h] = msg
    return list(seen.values())


def compute_window_start(
    last_digest_at: Optional[datetime],
    max_hours: int,
    now: Optional[datetime] = None,
) -> datetime:
    if now is None:
        now = datetime.utcnow()
    if last_digest_at is None:
        return now - timedelta(hours=24)
    return max(last_digest_at, now - timedelta(hours=max_hours))


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
        window_start: Optional[datetime] = None,
        interests_embedding: Optional[list[float]] = None,
    ) -> list[dict]:
        # Stage 1: pgvector similarity search
        if interests_embedding is not None:
            query_vector = interests_embedding
        else:
            embed_result = await self.embedding_service.embed_text(interests)
            query_vector = embed_result.embeddings[0]

        stmt = (
            select(Message)
            .where(Message.channel_id.in_(channel_ids))
            .where(Message.embedding.isnot(None))
        )
        if window_start:
            stmt = stmt.where(Message.date >= window_start)
        stmt = stmt.order_by(
            Message.embedding.cosine_distance(query_vector)
        ).limit(self.candidates_limit)
        result = await session.execute(stmt)
        candidates = result.scalars().all()
        candidates = deduplicate_candidates(candidates)

        if not candidates:
            return []

        # Stage 2: LLM ranking
        messages_for_llm = [{"id": m.id, "text": m.text} for m in candidates]
        llm_result = await self.llm_provider.rank_messages(
            messages=messages_for_llm,
            user_interests=interests,
            limit=self.digest_size,
        )

        return llm_result.ranked
