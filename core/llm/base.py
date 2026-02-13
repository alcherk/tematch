from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResult:
    ranked: list[dict]
    tokens_in: int
    tokens_out: int


class LLMProvider(ABC):
    @abstractmethod
    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        """Rank messages by relevance. Returns LLMResult."""
        ...


def create_llm_provider(provider: str, api_key: str) -> LLMProvider:
    if provider == "openai":
        from core.llm.openai_provider import OpenAIProvider

        return OpenAIProvider(api_key=api_key)
    elif provider == "claude":
        from core.llm.claude_provider import ClaudeProvider

        return ClaudeProvider(api_key=api_key)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
