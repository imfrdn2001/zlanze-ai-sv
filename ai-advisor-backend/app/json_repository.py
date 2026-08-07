import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.schemas import DeveloperMatch, Estimate


def _normalized(value: str) -> str:
    value = value.lower().replace(".js", "js").replace("/", " ")
    return " ".join(re.sub(r"[^a-z0-9+#. -]", " ", value).split())


def _terms(values: list[str]) -> list[str]:
    return list(dict.fromkeys(term for value in values if (term := _normalized(value))))


def _contains(term: str, text: str) -> bool:
    return term in text or term.replace(" ", "") in text.replace(" ", "")


def _aliases(term: str) -> list[str]:
    compact = term.replace(" ", "").replace(".", "")
    if compact in {"dotnet", "dotnetframework", "net", "netframework"}:
        return [term, "dot net", "net framework", "asp net", "c#"]
    return [term]


def _experience_years(value: object) -> float | None:
    text = str(value or "").lower()
    years = re.search(r"(\d+(?:\.\d+)?)\s*y", text)
    months = re.search(r"(\d+(?:\.\d+)?)\s*m", text)
    if not years and not months:
        return None
    return (float(years.group(1)) if years else 0) + (
        float(months.group(1)) / 12 if months else 0
    )


def _compensation_rates(value: object) -> tuple[float, float, float] | None:
    """Convert lakhs/year to INR rates, including the ₹150 hourly addition."""
    text = str(value or "").replace(",", "")
    amount = re.search(r"(\d+(?:\.\d+)?)", text)
    if not amount:
        return None
    annual_inr = float(amount.group(1)) * 100_000
    hourly_inr = annual_inr / 200 / 8 + 150
    daily_inr = hourly_inr * 8
    return annual_inr, daily_inr, hourly_inr


@dataclass
class JsonCandidateRepository:
    path: str
    currency: str = "INR"
    _profiles: list[dict[str, object]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        payload = json.loads(Path(self.path).read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("Candidate profile JSON must contain an array")
        # Retain only public matching/display fields. Email and phone are
        # intentionally never stored on this repository instance.
        allowed = {
            "name",
            "experience",
            "price",
            "location",
            "current_company",
            "education",
            "preferred_location",
            "skills",
            "profile_photo",
            "summary",
        }
        self._profiles = [
            {key: row.get(key) for key in allowed}
            for row in payload
            if isinstance(row, dict)
        ]

    @property
    def profile_count(self) -> int:
        return len(self._profiles)

    def _ranked(
        self,
        skills: list[str],
        project_type: str | None,
        min_experience_years: float | None = None,
    ) -> list[DeveloperMatch]:
        requested = _terms(skills or ([project_type] if project_type else []))
        if not requested:
            return []
        matches: list[DeveloperMatch] = []
        for index, profile in enumerate(self._profiles, start=1):
            compensation = _compensation_rates(profile.get("price"))
            experience_years = _experience_years(profile.get("experience"))
            if min_experience_years is not None and (
                experience_years is None or experience_years < min_experience_years
            ):
                continue
            fields = {
                "profile skills": _normalized(str(profile.get("skills") or "")),
                "professional summary": _normalized(str(profile.get("summary") or "")),
                "current role": _normalized(str(profile.get("current_company") or "")),
                "education": _normalized(str(profile.get("education") or "")),
            }
            evidence = {
                term: [
                    source
                    for source, text in fields.items()
                    if any(_contains(alias, text) for alias in _aliases(term))
                ]
                for term in requested
            }
            evidence = {term: sources for term, sources in evidence.items() if sources}
            if not evidence:
                continue
            coverage = round(len(evidence) / len(requested) * 100)
            evidence_weight = sum(
                5 if "profile skills" in sources else
                3 if "professional summary" in sources else
                2 if "current role" in sources else 1
                for sources in evidence.values()
            )
            matches.append(
                DeveloperMatch(
                    user_id=index,
                    display_name=str(profile.get("name") or "Candidate"),
                    profile_picture=str(profile.get("profile_photo") or "") or None,
                    skills=str(profile.get("skills") or ""),
                    matched_tech=list(evidence),
                    requested_tech_count=len(requested),
                    coverage_percent=coverage,
                    score=round(coverage + evidence_weight, 2),
                    match_evidence=evidence,
                    compensation_label=str(profile.get("price") or "") or None,
                    price_currency=self.currency,
                    annual_compensation_inr=compensation[0] if compensation else None,
                    daily_rate_inr=compensation[1] if compensation else None,
                    hourly_rate_inr=compensation[2] if compensation else None,
                    experience=str(profile.get("experience") or "") or None,
                    location=str(profile.get("location") or "") or None,
                    current_company=str(profile.get("current_company") or "") or None,
                )
            )
        return sorted(
            matches,
            key=lambda item: (
                item.coverage_percent,
                _experience_years(item.experience) or 0,
                item.score,
            ),
            reverse=True,
        )

    def find_developers(
        self,
        technologies: list[str],
        project_type: str | None,
        limit: int,
        min_experience_years: float | None = None,
    ) -> list[DeveloperMatch]:
        return self._ranked(
            technologies,
            project_type,
            min_experience_years,
        )[:limit]

    def count_freelancers(
        self,
        skills: list[str],
        project_type: str | None = None,
        min_experience_years: float | None = None,
    ) -> int:
        return sum(
            match.coverage_percent >= 50
            for match in self._ranked(skills, project_type, min_experience_years)
        )

    def estimate_cost(
        self,
        technologies: list[str],
        project_type: str | None,
    ) -> Estimate | None:
        return None

    def estimate_time(
        self,
        technologies: list[str],
        project_type: str | None,
    ) -> Estimate | None:
        return None
