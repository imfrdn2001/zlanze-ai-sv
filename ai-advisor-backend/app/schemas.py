from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class Intent(StrEnum):
    FIND_DEVELOPER = "find_developer"
    ESTIMATE_COST = "estimate_cost"
    ESTIMATE_TIME = "estimate_time"
    SUGGEST_TECHNOLOGY = "suggest_technology"
    EXPLAIN_PROJECT = "explain_project"
    COUNT_TALENT = "count_talent"


class ChatContext(BaseModel):
    project_type: str | None = None
    required_tech: list[str] = Field(default_factory=list)
    suggested_tech: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    budget: float | None = Field(default=None, ge=0)
    deadline_days: int | None = Field(default=None, ge=1)
    min_experience_years: float | None = Field(default=None, ge=0)
    pending_intents: list[Intent] = Field(default_factory=list)
    pending_clarification: str | None = None


class ScopeOptionSpec(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=300)
    project_type: str = Field(min_length=1, max_length=200)
    suggested_tech: list[str] = Field(min_length=1, max_length=5)

    @field_validator("suggested_tech")
    @classmethod
    def normalize_option_tech(cls, values: list[str]) -> list[str]:
        return list(
            dict.fromkeys(value.strip().lower() for value in values if value.strip())
        )


class ExtractedSlots(ChatContext):
    intents: list[Intent] = Field(min_length=1)
    tech_was_mentioned: bool = False
    technology_rationale: str | None = Field(default=None, max_length=500)
    advisory_response: str | None = Field(default=None, max_length=2000)
    needs_clarification: bool = False
    clarification_question: str | None = None
    scope_options: list[ScopeOptionSpec] = Field(default_factory=list, max_length=4)

    @field_validator("required_tech", "suggested_tech", "required_skills")
    @classmethod
    def normalize_tech(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for value in values:
            normalized = value.strip().lower()
            if normalized and normalized not in seen:
                seen.add(normalized)
                result.append(normalized)
        return result


class ChatRequest(BaseModel):
    chat_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
    query: str = Field(min_length=1, max_length=4000)


class DeveloperMatch(BaseModel):
    user_id: int
    display_name: str
    profile_picture: str | None = None
    skills: str
    level: str | None = None
    rating: float | None = None
    review_count: int = 0
    matched_tech: list[str] = Field(default_factory=list)
    requested_tech_count: int = 0
    coverage_percent: int = 0
    gig_count: int = 0
    score: float
    match_evidence: dict[str, list[str]] = Field(default_factory=dict)
    advertised_price_low: float | None = None
    advertised_price_high: float | None = None
    price_currency: str = "USD"
    compensation_label: str | None = None
    annual_compensation_inr: float | None = None
    daily_rate_inr: float | None = None
    hourly_rate_inr: float | None = None
    experience: str | None = None
    location: str | None = None
    current_company: str | None = None


class Estimate(BaseModel):
    low: float
    median: float
    high: float
    sample_size: int
    confidence: str
    data_volume: str
    relevance: str
    unit: str
    source: str


class ChatData(BaseModel):
    developers: list[DeveloperMatch] = Field(default_factory=list)
    cost: Estimate | None = None
    time: Estimate | None = None
    technology_used: list[str] = Field(default_factory=list)
    options: list["ProjectOption"] = Field(default_factory=list)
    total_matches: int | None = None
    search_terms: list[str] = Field(default_factory=list)


class ProjectOption(BaseModel):
    name: str
    description: str
    technology_used: list[str]
    developers: list[DeveloperMatch] = Field(default_factory=list)
    cost: Estimate | None = None
    time: Estimate | None = None


class ChatResponse(BaseModel):
    chat_id: str
    response: str
    intents: list[Intent]
    data: ChatData
    context: ChatContext
