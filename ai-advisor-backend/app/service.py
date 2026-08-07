import asyncio
import logging
import time

from app.context import ContextStore
from app.llm import GeminiExtractor
from app.repository import AdvisorRepository
from app.scope import enforce_scope_clarification, requests_all_pending_options
from app.schemas import ChatData, ChatResponse, ExtractedSlots, Intent, ProjectOption
from app.stack import normalize_suggested_stack
from app.templates import build_options_response, build_response

logger = logging.getLogger("ai_advisor.query")


class AdvisorService:
    def __init__(
        self,
        context_store: ContextStore,
        extractor: GeminiExtractor,
        repository: AdvisorRepository,
        max_developers: int,
        log_chat_content: bool = True,
    ) -> None:
        self.context_store = context_store
        self.extractor = extractor
        self.repository = repository
        self.max_developers = max_developers
        self.log_chat_content = log_chat_content

    async def chat(self, chat_id: str, query: str) -> ChatResponse:
        started = time.perf_counter()
        context = await self.context_store.get(chat_id)
        slots, token_count = await self.extractor.extract(query, context)
        if requests_all_pending_options(query, context.pending_clarification):
            return await self._compare_scope_options(
                chat_id, query, slots, token_count, started
            )
        return await self.chat_from_extraction(
            chat_id,
            slots,
            token_count,
            started,
            query=query,
        )

    async def _compare_scope_options(
        self,
        chat_id: str,
        query: str,
        slots: ExtractedSlots,
        token_count: int | None,
        started: float,
    ) -> ChatResponse:
        fallback_specs = [
            (
                "Informational business website",
                "Service pages, company information, contact details, and lead forms.",
                ["wordpress"],
                "informational business website",
            ),
            (
                "Online store",
                "Product catalogue, cart, checkout, payments, and order management.",
                ["shopify"],
                "online store with catalogue and checkout",
            ),
            (
                "Custom client portal",
                "Customer accounts, secure dashboards, bookings, and custom workflows.",
                ["react", "node.js", "postgresql"],
                "custom client portal with accounts and booking",
            ),
        ]
        option_specs = [
            (
                option.name,
                option.description,
                normalize_suggested_stack(
                    option.project_type,
                    option.suggested_tech,
                ),
                option.project_type,
            )
            for option in slots.scope_options
            if option.suggested_tech
        ]
        if len(option_specs) < 2:
            option_specs = fallback_specs

        async def load_option(
            name: str,
            description: str,
            technologies: list[str],
            project_type: str,
        ) -> ProjectOption:
            developers, cost = await asyncio.gather(
                asyncio.to_thread(
                    self.repository.find_developers,
                    technologies,
                    project_type,
                    self.max_developers,
                ),
                asyncio.to_thread(
                    self.repository.estimate_cost,
                    technologies,
                    project_type,
                ),
            )
            return ProjectOption(
                name=name,
                description=description,
                technology_used=technologies,
                developers=developers,
                cost=cost,
            )

        options = await asyncio.gather(
            *(load_option(*option_spec) for option_spec in option_specs)
        )
        resumed_intents = list(
            dict.fromkeys(
                [
                    *slots.intents,
                    Intent.SUGGEST_TECHNOLOGY,
                    Intent.FIND_DEVELOPER,
                    Intent.ESTIMATE_COST,
                ]
            )
        )
        completed_slots = slots.model_copy(
            update={
                "intents": resumed_intents,
                "needs_clarification": False,
                "clarification_question": None,
            }
        )
        context = await self.context_store.update(chat_id, completed_slots)
        data = ChatData(options=options)
        response_text = build_options_response(options)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "chat_scope_options_compared",
            extra={
                "chat_id": chat_id,
                "query": query if self.log_chat_content else None,
                "response": response_text if self.log_chat_content else None,
                "intents": [intent.value for intent in resumed_intents],
                "option_count": len(options),
                "options": [
                    {
                        "name": option.name,
                        "technology_used": option.technology_used,
                        "developer_count": len(option.developers),
                        "cost_estimate": (
                            option.cost.model_dump(mode="json") if option.cost else None
                        ),
                    }
                    for option in options
                ],
                "token_count": token_count,
                "latency_ms": duration_ms,
            },
        )
        logger.info("advisor_response\n%s", response_text)
        return ChatResponse(
            chat_id=chat_id,
            response=response_text,
            intents=resumed_intents,
            data=data,
            context=context,
        )

    async def chat_from_extraction(
        self,
        chat_id: str,
        slots: ExtractedSlots,
        token_count: int | None = None,
        started: float | None = None,
        query: str | None = None,
    ) -> ChatResponse:
        """Run database and response stages for already-extracted LLM slots."""
        started = started or time.perf_counter()
        previous_context = await self.context_store.get(chat_id)
        slots = enforce_scope_clarification(
            slots,
            has_pending_intents=bool(previous_context.pending_intents),
        )
        if previous_context.pending_intents:
            if slots.needs_clarification:
                slots = slots.model_copy(
                    update={"intents": previous_context.pending_intents}
                )
            else:
                resumed_intents = list(
                    dict.fromkeys([*previous_context.pending_intents, *slots.intents])
                )
                slots = slots.model_copy(update={"intents": resumed_intents})

        project_type = slots.project_type or previous_context.project_type
        normalized_stack = normalize_suggested_stack(
            project_type,
            slots.suggested_tech,
        )
        if normalized_stack != slots.suggested_tech:
            slots = slots.model_copy(update={"suggested_tech": normalized_stack})
        context = await self.context_store.update(chat_id, slots)
        technologies = slots.required_tech if slots.tech_was_mentioned else (
            slots.suggested_tech or context.suggested_tech or context.required_tech
        )
        search_terms = slots.required_skills or context.required_skills or technologies

        data = ChatData(technology_used=technologies, search_terms=search_terms)
        if not slots.needs_clarification:
            tasks: dict[str, asyncio.Task] = {}
            if Intent.FIND_DEVELOPER in slots.intents:
                tasks["developers"] = asyncio.create_task(
                    asyncio.to_thread(
                        self.repository.find_developers,
                        search_terms,
                        context.project_type,
                        self.max_developers,
                        context.min_experience_years,
                    )
                )
            if Intent.COUNT_TALENT in slots.intents:
                tasks["total_matches"] = asyncio.create_task(
                    asyncio.to_thread(
                        self.repository.count_freelancers,
                        search_terms,
                        context.project_type,
                        context.min_experience_years,
                    )
                )
            if Intent.ESTIMATE_COST in slots.intents:
                tasks["cost"] = asyncio.create_task(
                    asyncio.to_thread(
                        self.repository.estimate_cost,
                        technologies,
                        context.project_type,
                    )
                )
            if Intent.ESTIMATE_TIME in slots.intents:
                tasks["time"] = asyncio.create_task(
                    asyncio.to_thread(
                        self.repository.estimate_time,
                        technologies,
                        context.project_type,
                    )
                )
            for key, task in tasks.items():
                setattr(data, key, await task)

        response_text = build_response(slots, context, data)
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        logger.info(
            "chat_turn_completed",
            extra={
                "chat_id": chat_id,
                "query": query if self.log_chat_content else None,
                "response": response_text if self.log_chat_content else None,
                "intents": [intent.value for intent in slots.intents],
                "project_type": context.project_type,
                "required_tech": context.required_tech,
                "suggested_tech": context.suggested_tech,
                "required_skills": context.required_skills,
                "min_experience_years": context.min_experience_years,
                "needs_clarification": slots.needs_clarification,
                "pending_intents": [
                    intent.value for intent in context.pending_intents
                ],
                "developer_count": len(data.developers),
                "total_matches": data.total_matches,
                "developer_ids": [developer.user_id for developer in data.developers],
                "cost_estimate": (
                    data.cost.model_dump(mode="json") if data.cost else None
                ),
                "time_estimate": (
                    data.time.model_dump(mode="json") if data.time else None
                ),
                "token_count": token_count,
                "latency_ms": duration_ms,
            },
        )
        logger.info("advisor_response\n%s", response_text)
        return ChatResponse(
            chat_id=chat_id,
            response=response_text,
            intents=slots.intents,
            data=data,
            context=context,
        )
