import json
import logging
import re

from openai import AsyncOpenAI

from core.llm.base import LLMProvider, LLMResult

logger = logging.getLogger(__name__)

RANK_PROMPT = """You are a content recommendation engine.
Given a user's interests and a list of messages, rank the messages by relevance.

User interests: {interests}

Messages:
{messages}

Return a JSON array of the top {limit} message IDs sorted by relevance, with scores 0-1:
[{{"message_id": 1, "score": 0.95}}, ...]
Return ONLY the JSON array, no other text."""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def rank_messages(
        self, messages: list[dict], user_interests: str, limit: int
    ) -> LLMResult:
        msg_text = "\n".join(f"[ID={m['id']}] {m['text'][:300]}" for m in messages)
        prompt = RANK_PROMPT.format(
            interests=user_interests, messages=msg_text, limit=limit
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        usage = response.usage
        content = response.choices[0].message.content or ""
        # Strip markdown fences if present
        match = re.search(r"\[.*\]", content, re.DOTALL)
        if match:
            ranked = json.loads(match.group())
        else:
            logger.error("LLM returned unparseable response: %s", content[:500])
            ranked = []
        return LLMResult(
            ranked=ranked,
            tokens_in=usage.prompt_tokens if usage else 0,
            tokens_out=usage.completion_tokens if usage else 0,
        )
