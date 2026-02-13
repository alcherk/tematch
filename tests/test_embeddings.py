from unittest.mock import AsyncMock

import pytest

from core.embeddings import EmbeddingService


@pytest.mark.asyncio
async def test_embed_text_returns_vector():
    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = AsyncMock(
        data=[AsyncMock(embedding=[0.1] * 1536)]
    )
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = mock_client
    service.model = "text-embedding-3-small"
    service.dim = 1536

    result = await service.embed_text("hello world")
    assert len(result) == 1536
    assert result[0] == 0.1


@pytest.mark.asyncio
async def test_embed_texts_batch():
    mock_client = AsyncMock()
    mock_client.embeddings.create.return_value = AsyncMock(
        data=[
            AsyncMock(embedding=[0.1] * 1536),
            AsyncMock(embedding=[0.2] * 1536),
        ]
    )
    service = EmbeddingService.__new__(EmbeddingService)
    service.client = mock_client
    service.model = "text-embedding-3-small"
    service.dim = 1536

    result = await service.embed_texts(["hello", "world"])
    assert len(result) == 2
