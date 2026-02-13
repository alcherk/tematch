
from openai import AsyncOpenAI


class EmbeddingService:
    def __init__(
        self, api_key: str, model: str = "text-embedding-3-small", dim: int = 1536
    ):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dim = dim

    async def embed_text(self, text: str) -> list[float]:
        response = await self.client.embeddings.create(
            model=self.model, input=text, dimensions=self.dim
        )
        return response.data[0].embedding

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        response = await self.client.embeddings.create(
            model=self.model, input=texts, dimensions=self.dim
        )
        return [d.embedding for d in response.data]
