#!/usr/bin/env python3
"""Exercise the complete advisor pipeline without FastAPI or Redis."""

import argparse
import asyncio
import json

import httpx

from app.config import get_settings
from app.database import create_database_engine
from app.llm import GeminiExtractor
from app.repository import AdvisorRepository
from app.schemas import ChatContext, ExtractedSlots
from app.service import AdvisorService


class MemoryContextStore:
    """Small local context store for multi-turn command-line testing."""

    def __init__(self) -> None:
        self.contexts: dict[str, ChatContext] = {}

    async def get(self, chat_id: str) -> ChatContext:
        return self.contexts.get(chat_id, ChatContext())

    async def update(self, chat_id: str, slots: ExtractedSlots) -> ChatContext:
        existing = await self.get(chat_id)
        updates = slots.model_dump(
            include={
                "project_type",
                "required_tech",
                "suggested_tech",
                "budget",
                "deadline_days",
            },
            exclude_none=True,
        )
        updates = {key: value for key, value in updates.items() if value != []}
        merged = existing.model_copy(update=updates)
        self.contexts[chat_id] = merged
        return merged


def local_database_url(database_url: str) -> str:
    """Translate the Compose hostname for a host-side test run."""
    return database_url.replace("@zlanze-sqlserver:", "@127.0.0.1:")


async def run_query(query: str, chat_id: str) -> None:
    settings = get_settings()
    if not settings.gemini_api_key:
        raise SystemExit("GEMINI_API_KEY is empty in .env")

    engine = create_database_engine(
        local_database_url(settings.database_url),
        settings.sql_query_timeout_seconds,
    )
    context_store = MemoryContextStore()
    async with httpx.AsyncClient(timeout=20) as client:
        extractor = GeminiExtractor(settings.gemini_api_key, settings.gemini_model, client)
        advisor = AdvisorService(
            context_store,
            extractor,
            AdvisorRepository(engine),
            settings.max_developers,
        )
        context = await context_store.get(chat_id)
        extraction, token_count = await extractor.extract(query, context)
        result = await advisor.chat_from_extraction(chat_id, extraction, token_count)

    engine.dispose()
    print("\nGemini extraction\n")
    print(json.dumps(extraction.model_dump(mode="json"), indent=2))
    if token_count is not None:
        print(f"\nGemini tokens used: {token_count}")
    print("\nAdvisor response\n")
    print(result.response)
    print("\nStructured result\n")
    print(json.dumps(result.model_dump(mode="json"), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "query",
        nargs="?",
        default=(
            "I need an ecommerce website using React and Python. "
            "Find developers and estimate the cost and delivery time."
        ),
    )
    parser.add_argument("--chat-id", default="local-cli-test")
    args = parser.parse_args()
    try:
        asyncio.run(run_query(args.query, args.chat_id))
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        try:
            detail = exc.response.json().get("error", {}).get("message", "")
        except (ValueError, AttributeError):
            detail = ""
        message = f"Gemini request failed with HTTP {status}."
        if detail:
            message += f" {detail}"
        raise SystemExit(message) from None
    except httpx.RequestError as exc:
        raise SystemExit(f"Could not reach Gemini: {exc.__class__.__name__}") from None


if __name__ == "__main__":
    main()
