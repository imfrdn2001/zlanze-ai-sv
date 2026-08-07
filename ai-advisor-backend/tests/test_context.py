import fakeredis.aioredis
import pytest

from app.context import RedisContextStore
from app.schemas import ExtractedSlots, Intent


@pytest.mark.asyncio
async def test_clarification_intents_are_stored_then_cleared() -> None:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    store = RedisContextStore(redis, ttl_seconds=60)

    awaiting_answer = ExtractedSlots(
        intents=[Intent.FIND_DEVELOPER],
        project_type="textile website",
        needs_clarification=True,
        clarification_question="Catalogue or store?",
    )
    context = await store.update("chat-1", awaiting_answer)
    assert context.pending_intents == [Intent.FIND_DEVELOPER]
    assert context.pending_clarification == "Catalogue or store?"

    clarification_answer = ExtractedSlots(
        intents=[Intent.SUGGEST_TECHNOLOGY],
        project_type="standard online store",
        suggested_tech=["shopify"],
    )
    context = await store.update("chat-1", clarification_answer)
    assert context.pending_intents == []
    assert context.pending_clarification is None

    await redis.aclose()
