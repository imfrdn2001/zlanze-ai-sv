import json

import httpx

from app.schemas import ChatContext, ExtractedSlots


SYSTEM_INSTRUCTION = """You extract intent and project requirements for a freelance
marketplace advisor. Return JSON matching the supplied schema and nothing else.

Rules:
- Valid intents are find_developer, estimate_cost, estimate_time,
  suggest_technology, explain_project, and count_talent.
- Intents describe only what the CURRENT message asks for. Do not carry intents
  forward from cached context.
- Cached pending_intents means the previous turn asked a clarification. Classify
  the current answer normally; deterministic code will resume those pending intents.
- Do not infer cost or time merely because the client describes a project.
- "Suggest a developer", "who can build this", or similar means find_developer only.
- Questions containing "how many", "number of", "count", or "are there" about
  available freelancers include count_talent. If they also ask "who", include
  find_developer so the response contains both the total and top matches.
- Talent search is not limited to software development. Support designers,
  writers, marketers, video editors, consultants, and every other marketplace
  discipline. Put non-technology capabilities such as UI/UX design, graphic
  design, branding, illustration, SEO, or copywriting in required_skills.
- required_skills contains explicitly requested professional skills or service
  disciplines. required_tech contains only named software technologies.
- min_experience_years is the minimum total experience explicitly requested by
  the client (for example, "at least 2 years" means 2). Do not invent it.
- For direct talent inventory questions such as "how many graphic designers"
  or "who knows React", do not invent a project type or a full suggested stack.
- The word "suggest" does not mean suggest_technology when its object is a
  developer, freelancer, expert, person, or agency.
- "What will it cost" means estimate_cost only.
- "How long will it take" means estimate_time only.
- Requests for a stack, framework, database, architecture, or technology choice
  include suggest_technology.
- Requests to elaborate, explain the proposed website, describe how it works,
  suggest features, or discuss an idea include explain_project. Do not add
  suggest_technology unless the CURRENT message also asks about technology.
- For explain_project, write advisory_response as a useful, context-aware answer
  covering the requested concept, important features or workflow, and practical
  next decisions. Do not merely repeat the technology recommendation. Keep it
  concise and do not invent marketplace prices, delivery times, or developers.
- advisory_response must be null when explain_project is not an intent.
- Merely mentioning a technology while asking for cost, time, or developers does
  not include suggest_technology. Add it only when the client asks for technology
  advice, a recommendation, an explanation, or a stack/database choice.
- required_tech contains only technologies explicitly named by the client.
- suggested_tech contains a concise practical stack inferred from the project.
- suggested_tech must be one coherent, minimal architecture. Do not combine a
  turnkey commerce platform such as Shopify with React and Node.js unless the
  client explicitly needs a custom headless storefront or integration layer.
- For a standard online store with catalogue and cart, prefer the commerce
  platform alone plus only essential supporting technology. For a genuinely
  custom application, suggest a custom frontend, backend, and database stack.
- tech_was_mentioned is true only when the current message explicitly names technology.
- technology_rationale is one concise sentence explaining the suggested stack,
  but only when suggest_technology is an intent; otherwise return null.
- Preserve relevant supplied context unless the current message changes it.
- Preserve specific domain nouns such as textile, electrical, healthcare, or
  restaurant in project_type; do not reduce "electrical business website" to
  merely "website".
- Convert deadlines to a positive number of days when possible.
- Ask one concise clarification before cost, time, stack, or developer matching
  when a major scope distinction would materially change the result. For example,
  ask whether a generic business website is a catalogue, a standard online store,
  or a custom marketplace. Do not ask again when cached context answers it.
- When cached pending_intents and pending_clarification exist and the client asks
  what the offered choices mean or how they differ, they have NOT answered the
  clarification. Explain the exact scope choices in pending_clarification, not
  technologies from suggested_tech. Set needs_clarification=true and use
  clarification_question for that explanation followed by a request to choose.
  Do not select an option for them.
- When cached pending_intents and pending_clarification exist and the client asks
  for developers, costs, recommendations, or a comparison for "all", "each",
  "these", "both", or all three offered choices, populate scope_options with
  2–4 distinct choices appropriate to the business domain. Each option needs a
  concise name, description, specific project_type, and one coherent minimal
  suggested_tech stack. Set needs_clarification=false. Do not combine the
  options into one stack. For example, a turnkey store can use Shopify alone,
  while a custom portal can use a frontend, backend, and database.
- Otherwise scope_options must be an empty list.
- Never invent budget, deadline, or project type.
"""


class LLMConfigurationError(RuntimeError):
    pass


class LLMResponseError(RuntimeError):
    pass


class GeminiExtractor:
    def __init__(
        self,
        api_key: str,
        model: str,
        client: httpx.AsyncClient,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.client = client

    async def extract(
        self,
        query: str,
        context: ChatContext,
    ) -> tuple[ExtractedSlots, int | None]:
        if not self.api_key:
            raise LLMConfigurationError("GEMINI_API_KEY is not configured")

        prompt = (
            f"Cached context:\n{context.model_dump_json(exclude_none=True)}"
            f"\n\nCurrent client message:\n{query}"
        )
        response = await self.client.post(
            (
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{self.model}:generateContent"
            ),
            headers={"x-goog-api-key": self.api_key},
            json={
                "system_instruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                    "responseJsonSchema": ExtractedSlots.model_json_schema(),
                },
            },
        )
        response.raise_for_status()
        payload = response.json()
        try:
            text = payload["candidates"][0]["content"]["parts"][0]["text"]
            slots = ExtractedSlots.model_validate(json.loads(text))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise LLMResponseError("Gemini returned an invalid structured response") from exc

        token_count = payload.get("usageMetadata", {}).get("totalTokenCount")
        return slots, token_count
