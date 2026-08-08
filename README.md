# Zlanze AI Advisor Backend

Standalone FastAPI service for the freelance marketplace advisor. It does not
modify or depend on the existing Zlanze application source code.

## How it works

Each `/chat` request:

1. loads compact session context from Redis;
2. makes one Gemini call for intent extraction and slot filling;
3. queries the restored SQL Server database with a read-only account;
4. ranks freelancers by requested-stack coverage before reputation;
5. calculates robust price/time ranges from one representative value per gig;
6. separates estimate relevance from data-volume confidence;
7. returns a deterministic response template.

Names, skills, public marketplace ratings, gig descriptions, prices, and
delivery durations are used. Emails, phone numbers, passwords, and client
contact details are never selected or sent to Gemini.

When a project is too broad for meaningful matching, the advisor stores the
original intent as pending and asks one scope question. The next answer resumes
that original request automatically. Cost-only and time-only follow-ups do not
repeat unchanged developer or technology sections.

## Configuration

Copy `.env.example` to `.env`. Set `GEMINI_API_KEY` to a server-side Gemini API
key. The model name is configurable through `GEMINI_MODEL`.

The local development file is already configured for:

- the separate SQL Server on `localhost:1433`;
- database `ZLANZE_PROD`;
- read-only login `zlanze_ai_reader`;
- Redis in this project's Compose stack.

Never put production credentials in this file or commit `.env`.

## Start

Make sure the database stack in `../database` is running, then:

```bash
docker compose up --build -d
docker compose ps
```

The API is available at:

- API: `http://localhost:8001`
- OpenAPI UI: `http://localhost:8001/docs`
- health: `http://localhost:8001/health`

Example:

```bash
curl -X POST http://localhost:8001/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "chat_id": "demo-1",
    "query": "Find a React and Python developer and estimate cost and time"
  }'
```

Without `GEMINI_API_KEY`, health checks still work but `/chat` returns a clear
503 configuration response.

## Deploy to Azure Web App (Python runtime)

Deploy only the `ai-advisor-backend/` folder as the app root (e.g. via `az webapp
deploy --src-path .` from this directory, or a GitHub Action that uploads this
folder).

### What the repo already provides

- `requirements.txt` for the Oryx Python build — no Docker required.
- No hard dependency on Redis: with no `REDIS_URL` configured the service uses
  an in-memory context store, so it runs on a single App Service instance
  without extra infrastructure. Conversation context resets on restart or
  scale-out; configure Azure Cache for Redis (`REDIS_URL`) when you need
  persisted context across instances.
- Default `talent_data_source` is `json`, so the bundled candidate profiles are
  used and no SQL Server connection is required.

### App Settings to configure

Set these in the Azure portal (Configuration → Application settings):

| Setting                  | Value                                                          |
| ------------------------ | -------------------------------------------------------------- |
| `GEMINI_API_KEY`         | your Gemini API key                                            |
| `DATABASE_URL`           | only if you switch `TALENT_DATA_SOURCE` to `sql`               |
| `REDIS_URL`              | only if you use Azure Cache for Redis                          |
| `CORS_ORIGINS`           | comma-separated allowed frontend origins (overrides config)    |

### Startup command

Azure's Python build starts with gunicorn by default, but this is an ASGI app,
so set the **Startup Command** in the App Service configuration to:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Health check: `GET /health`. Docs: `GET /docs`.

## Test the advisor without running the API

The restored SQL Server must be running, but FastAPI and Redis are not needed:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
python scripts/test_advisor.py
```

Pass a custom client message as one quoted argument:

```bash
python scripts/test_advisor.py \
  "I need a Python automation tool. Who is available and what will it cost?"
```

The script uses an in-memory conversation context and prints both the
client-facing response and the complete structured result.

## Test

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## API contract

`POST /chat`

Request:

```json
{
  "chat_id": "session-identifier",
  "query": "I need an ecommerce website. Who should build it and what will it cost?"
}
```

Response includes the rendered `response`, extracted `intents`, structured
developer/estimate `data`, and compact cached `context`.

## Conversation logs

Each completed chat turn is appended as one JSON object to
`logs/advisor.jsonl`. The record includes the session ID, message and response,
intent, project type, selected stack, result counts, estimates, Gemini token
count, and total latency. This JSON Lines format can be searched directly or
loaded into Python, PostgreSQL, Elasticsearch, or an analytics tool.

Logs rotate at 10 MB and retain five backups by default. Configure this with
`LOG_FILE`, `LOG_MAX_BYTES`, and `LOG_BACKUP_COUNT`. Set
`LOG_CHAT_CONTENT=false` to retain operational metadata without storing user
messages or advisor responses. API keys and database credentials are never
written to these records.
