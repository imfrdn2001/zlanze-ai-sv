import json
import time
from typing import Protocol

from redis.asyncio import Redis

from app.schemas import ChatContext, ExtractedSlots


class ContextStore(Protocol):
    async def get(self, chat_id: str) -> ChatContext: ...

    async def update(self, chat_id: str, slots: ExtractedSlots) -> ChatContext: ...


def _merge_slots(existing: ChatContext, slots: ExtractedSlots) -> ChatContext:
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
    updates["pending_intents"] = slots.intents if slots.needs_clarification else []
    updates["pending_clarification"] = (
        slots.clarification_question if slots.needs_clarification else None
    )
    return existing.model_copy(update=updates)


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
        merged = _merge_slots(existing, slots)
        await self.redis.set(
            self._key(chat_id),
            merged.model_dump_json(),
            ex=self.ttl_seconds,
        )
        return merged


class InMemoryContextStore:
    """Process-local context store used when no Redis is configured.

    Safely serves a single App Service instance; conversation context resets on
    restart or scale-out. Suitable for development and single-instance Azure
    Web App deployments.
    """

    def __init__(self, ttl_seconds: int) -> None:
        self.ttl_seconds = ttl_seconds
        self._items: dict[str, tuple[float, ChatContext]] = {}

    async def get(self, chat_id: str) -> ChatContext:
        entry = self._items.get(chat_id)
        if not entry:
            return ChatContext()
        expires_at, existing = entry
        if expires_at <= time.monotonic():
            self._items.pop(chat_id, None)
            return ChatContext()
        return existing

    async def update(self, chat_id: str, slots: ExtractedSlots) -> ChatContext:
        existing = await self.get(chat_id)
        merged = _merge_slots(existing, slots)
        self._items[chat_id] = (time.monotonic() + self.ttl_seconds, merged)
        return merged
