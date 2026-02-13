from unittest.mock import AsyncMock, MagicMock

import pytest

from collector.embedding_buffer import EmbeddingBuffer


@pytest.mark.asyncio
async def test_buffer_accumulates_and_flushes():
    mock_session = AsyncMock()
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    mock_session_factory = MagicMock(return_value=mock_ctx)

    mock_embedding = AsyncMock()
    from core.embeddings import EmbeddingResult
    mock_embedding.embed_texts.return_value = EmbeddingResult(
        embeddings=[[0.1] * 1536, [0.2] * 1536],
        tokens=100,
    )

    buffer = EmbeddingBuffer(
        embedding_service=mock_embedding,
        session_factory=mock_session_factory,
        batch_size=2,
    )
    buffer.add(message_id=1, text="hello world message one")
    assert len(buffer._pending) == 1

    buffer.add(message_id=2, text="hello world message two")
    await buffer.flush()
    mock_embedding.embed_texts.assert_called_once()


def test_buffer_add_does_not_flush_below_threshold():
    buffer = EmbeddingBuffer(
        embedding_service=MagicMock(),
        session_factory=MagicMock(),
        batch_size=10,
    )
    buffer.add(message_id=1, text="hello")
    assert len(buffer._pending) == 1
