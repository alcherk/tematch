from __future__ import annotations

from dataclasses import dataclass

from openai import AsyncOpenAI


@dataclass
class EmbeddingResult:
    embeddings: list[list[float]]
    tokens: int


class EmbeddingService:
    def __init__(
        self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dim = dim

    async def embed_text(self, text: str) -> EmbeddingResult:
        response = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dim
        )
        return EmbeddingResult(
            embeddings=[response.data[0].embedding],
            tokens=response.usage.total_tokens if response.usage else 0,
        )

    async def embed_texts(self, texts: list[str]) -> EmbeddingResult:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return EmbeddingResult(
            embeddings=[d.embedding for d in response.data],
            tokens=response.usage.total_tokens if response.usage else 0,
        )
