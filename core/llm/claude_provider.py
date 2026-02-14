import json
import logging
import re

from anthropic import AsyncAnthropic

from core.llm.base import LLMProvider, LLMResult
from core.llm.openai_provider import RANK_PROMPT

logger = logging.getLogger(__name__)


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        self.client = AsyncAnthropic(api_key=api_key)
        self.model = model

    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        msg_text = "\n".join(f"[ID={m['id']}] {m['text'][:300]}" for m in messages)
        prompt = RANK_PROMPT.format(
            interests=user_interests, messages=msg_text, limit=limit
        )
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.content[0].text or ""
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            ranked = json.loads(match.group())
        else:
            logger.error("LLM returned unparseable response: %s", content[:500])
            ranked = []
        return LLMResult(
            ranked=ranked,
            tokens_in=response.usage.input_tokens,
            tokens_out=response.usage.output_tokens,
        )
