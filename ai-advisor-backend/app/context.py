import json
from typing import Protocol

from redis.asyncio import Redis

from app.schemas import ChatContext, ExtractedSlots


class ContextStore(Protocol):
    async def get(self, chat_id: str) -> ChatContext: ...

    async def update(self, chat_id: str, slots: ExtractedSlots) -> ChatContext: ...


class RedisContextStore:
    def __init__(self, redis: Redis, ttl_seconds: int) -> None:
        self.redis = redis
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _key(chat_id: str) -> str:
        return f"ai-advisor:chat:{chat_id}"

    async def get(self, chat_id: str) -> ChatContext:
        raw = await self.redis.get(self._key(chat_id))
        if not raw:
            return ChatContext()
        return ChatContext.model_validate(json.loads(raw))

    async def update(self, chat_id: str, slots: ExtractedSlots) -> ChatContext:
        existing = await self.get(chat_id)
        updates = slots.model_dump(
            include={
                "project_type",
                "required_tech",
                "suggested_tech",
                "required_skills",
                "budget",
                "deadline_days",
                "min_experience_years",
            },
            exclude_none=True,
        )
        # Empty inferred lists should not erase useful context from an earlier turn.
        updates = {key: value for key, value in updates.items() if value != []}
        updates["pending_intents"] = (
            slots.intents if slots.needs_clarification else []
        )
        updates["pending_clarification"] = (
            slots.clarification_question if slots.needs_clarification else None
        )
        merged = existing.model_copy(update=updates)
        await self.redis.set(
            self._key(chat_id),
            merged.model_dump_json(),
            ex=self.ttl_seconds,
        )
        return merged
