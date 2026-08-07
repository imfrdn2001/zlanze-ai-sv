import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import Settings, get_settings
from app.context import ContextStore, InMemoryContextStore, RedisContextStore
from app.database import create_database_engine
from app.llm import GeminiExtractor, LLMConfigurationError, LLMResponseError
from app.logging_config import configure_logging
from app.json_repository import JsonCandidateRepository
from app.repository import AdvisorRepository
from app.schemas import ChatRequest, ChatResponse
from app.service import AdvisorService


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        settings.log_level,
        settings.log_file,
        settings.log_max_bytes,
        settings.log_backup_count,
    )
    redis = None
    context_store: ContextStore | None = None
    if settings.redis_url:
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        context_store = RedisContextStore(redis, settings.context_ttl_seconds)
    else:
        context_store = InMemoryContextStore(settings.context_ttl_seconds)
    engine = None
    if settings.talent_data_source.lower() == "json":
        repository = JsonCandidateRepository(
            settings.candidate_profiles_file,
            settings.marketplace_currency,
        )
    else:
        engine = create_database_engine(
            settings.database_url,
            settings.sql_query_timeout_seconds,
        )
        repository = AdvisorRepository(engine, settings.marketplace_currency)
    http_client = httpx.AsyncClient(timeout=20)
    app.state.redis = redis
    app.state.engine = engine
    app.state.http_client = http_client
    app.state.advisor = AdvisorService(
        context_store,
        GeminiExtractor(settings.gemini_api_key, settings.gemini_model, http_client),
        repository,
        settings.max_developers,
        settings.log_chat_content,
    )
    yield
    await http_client.aclose()
    if redis is not None:
        await redis.aclose()
    if engine is not None:
        engine.dispose()


app = FastAPI(
    title="Zlanze AI Advisor API",
    version="0.1.0",
    lifespan=lifespan,
)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


def get_advisor(request: Request) -> AdvisorService:
    return request.app.state.advisor


@app.get("/health")
async def health(request: Request) -> dict[str, object]:
    checks: dict[str, bool] = {"api": True, "talent_data": False, "redis": False}
    if request.app.state.engine is None:
        checks["talent_data"] = bool(
            getattr(request.app.state.advisor.repository, "profile_count", 0)
        )
    else:
        try:
            with request.app.state.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            checks["talent_data"] = True
        except SQLAlchemyError:
            pass
    try:
        if request.app.state.redis is None:
            checks["redis"] = True
        else:
            checks["redis"] = bool(await request.app.state.redis.ping())
    except Exception:
        pass
    healthy = all(checks.values())
    return {"status": "ok" if healthy else "degraded", "checks": checks}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    advisor: AdvisorService = Depends(get_advisor),
) -> ChatResponse:
    try:
        return await advisor.chat(payload.chat_id, payload.query)
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except (LLMResponseError, httpx.HTTPError) as exc:
        logging.getLogger("ai_advisor").exception("LLM request failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model could not process this request.",
        ) from exc
    except SQLAlchemyError as exc:
        logging.getLogger("ai_advisor").exception("Database query failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The marketplace database is temporarily unavailable.",
        ) from exc
