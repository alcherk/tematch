import json

from openai import AsyncOpenAI

from core.llm.base import LLMProvider

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
    ) -> list[dict]:
        msg_text = "\n".join(f"[ID={m['id']}] {m['text'][:300]}" for m in messages)
        prompt = RANK_PROMPT.format(
            interests=user_interests, messages=msg_text, limit=limit
        )
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        return json.loads(response.choices[0].message.content)
