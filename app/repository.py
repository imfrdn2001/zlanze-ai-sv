import re
import statistics
from math import ceil
from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import Integer, bindparam, text
from sqlalchemy.engine import Engine, RowMapping

from app.schemas import DeveloperMatch, Estimate


def _safe_terms(terms: Iterable[str]) -> list[str]:
    result: list[str] = []
    for term in terms:
        # Treat separators as spaces so "UI/UX" matches marketplace labels such
        # as "UI UX Design" instead of collapsing into the unsearchable "uiux".
        normalized = re.sub(
            r"[^a-zA-Z0-9+#. -]",
            " ",
            term,
        )
        normalized = " ".join(normalized.lower().split())
        if len(normalized) >= 2 and normalized not in result:
            result.append(normalized)
    return result[:12]


def _confidence(sample_size: int) -> str:
    if sample_size >= 30:
        return "high"
    if sample_size >= 10:
        return "medium"
    return "low"


PROJECT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "app",
    "application",
    "build",
    "business",
    "for",
    "my",
    "of",
    "online",
    "platform",
    "project",
    "site",
    "system",
    "the",
    "to",
    "website",
}


def _project_terms(project_type: str | None) -> list[str]:
    if not project_type:
        return []
    words = re.findall(r"[a-zA-Z0-9+#.]+", project_type.lower())
    return _safe_terms(
        word for word in words if len(word) >= 3 and word not in PROJECT_STOP_WORDS
    )[:5]


def _relevance_label(coverage_ratio: float, project_match: bool) -> str:
    if coverage_ratio >= 0.8 and project_match:
        return "high"
    if coverage_ratio >= 0.6:
        return "medium"
    return "low"


def _overall_confidence(sample_size: int, relevance: str) -> str:
    if sample_size >= 20 and relevance == "high":
        return "high"
    if sample_size >= 10 and relevance in {"high", "medium"}:
        return "medium"
    return "low"


def _percentile(values: list[float], fraction: float) -> float:
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    weight = position - lower
    return values[lower] * (1 - weight) + values[upper] * weight


@dataclass
class AdvisorRepository:
    engine: Engine
    currency: str = "USD"

    def find_developers(
        self,
        technologies: list[str],
        project_type: str | None,
        limit: int,
        min_experience_years: float | None = None,
    ) -> list[DeveloperMatch]:
        terms = _safe_terms(technologies)
        if not terms and project_type:
            terms = _safe_terms([project_type])
        if not terms:
            return []

        predicates: list[str] = []
        source_predicates: list[dict[str, str]] = []
        params: dict[str, object] = {"limit": limit}
        for index, term in enumerate(terms):
            key = f"term_{index}"
            sources = {
                "profile_skills": f"LOWER(COALESCE(f.Skills, '')) LIKE :{key}",
                "gig_title": f"LOWER(COALESCE(g.GigTitle, '')) LIKE :{key}",
                "search_tags": f"LOWER(COALESCE(g.SearchTags, '')) LIKE :{key}",
                "gig_description": f"LOWER(COALESCE(g.Description, '')) LIKE :{key}",
                "package_description": (
                    f"(LOWER(COALESCE(p.BasicDesc, '')) LIKE :{key} "
                    f"OR LOWER(COALESCE(p.StandardDesc, '')) LIKE :{key} "
                    f"OR LOWER(COALESCE(p.PremiumDesc, '')) LIKE :{key})"
                ),
                "category": f"LOWER(COALESCE(c.CategoryDesc, '')) LIKE :{key}",
            }
            source_predicates.append(sources)
            predicates.append("(" + " OR ".join(sources.values()) + ")")
            params[key] = f"%{term}%"

        match_columns = [
            f"MAX(CASE WHEN {predicate} THEN 1 ELSE 0 END)"
            for predicate in predicates
        ]
        match_score = " + ".join(match_columns)
        match_select = ",\n                ".join(
            f"{column} AS Match{index}"
            for index, column in enumerate(match_columns)
        )
        evidence_select = ",\n                ".join(
            f"MAX(CASE WHEN {predicate} THEN 1 ELSE 0 END) "
            f"AS Evidence{index}_{source}"
            for index, sources in enumerate(source_predicates)
            for source, predicate in sources.items()
        )
        evidence_score = " + ".join(
            "MAX(CASE "
            f"WHEN {sources['profile_skills']} THEN 5 "
            f"WHEN {sources['gig_title']} THEN 4 "
            f"WHEN {sources['search_tags']} THEN 4 "
            f"WHEN {sources['gig_description']} THEN 2 "
            f"WHEN {sources['package_description']} THEN 1 "
            f"WHEN {sources['category']} THEN 1 ELSE 0 END)"
            for sources in source_predicates
        )
        query = text(
            f"""
            SELECT TOP (:limit)
                f.UserID,
                COALESCE(NULLIF(f.DisplayName, ''), 'Freelancer') AS DisplayName,
                f.ProfilePicture,
                COALESCE(f.Skills, '') AS Skills,
                f.Level,
                CAST(f.AvgRatings AS float) AS AvgRatings,
                COALESCE(f.NumberOfReviews, 0) AS NumberOfReviews,
                COUNT(DISTINCT g.GigID) AS GigCount,
                MIN(CASE
                    WHEN p.BasicPrice > 0 THEN CAST(p.BasicPrice AS float)
                    WHEN p.StandardPrice > 0 THEN CAST(p.StandardPrice AS float)
                    WHEN p.PremiumPrice > 0 THEN CAST(p.PremiumPrice AS float)
                END) AS AdvertisedPriceLow,
                MAX(CASE
                    WHEN p.PremiumPrice > 0 THEN CAST(p.PremiumPrice AS float)
                    WHEN p.StandardPrice > 0 THEN CAST(p.StandardPrice AS float)
                    WHEN p.BasicPrice > 0 THEN CAST(p.BasicPrice AS float)
                END) AS AdvertisedPriceHigh,
                {match_score} AS SkillMatchCount,
                {match_select},
                {evidence_select}
            FROM AIADVISOR.Freelancers AS f
            LEFT JOIN AIADVISOR.Gigs AS g ON g.Userid = f.UserID
            LEFT JOIN AIADVISOR.GigPrices AS p ON p.GigID = g.GigID
            LEFT JOIN AIADVISOR.Categories AS c ON c.CategoryID = g.CategoryID
            WHERE {" OR ".join(predicates)}
            GROUP BY
                f.UserID, f.DisplayName, f.ProfilePicture, f.Skills, f.Level,
                f.AvgRatings, f.NumberOfReviews
            ORDER BY
                {match_score} DESC,
                CASE WHEN COUNT(DISTINCT g.GigID) > 0 THEN 1 ELSE 0 END DESC,
                {evidence_score} DESC,
                COALESCE(f.AvgRatings, 0) DESC,
                COALESCE(f.NumberOfReviews, 0) DESC,
                COUNT(DISTINCT g.GigID) DESC
            """
        ).bindparams(bindparam("limit", type_=Integer, literal_execute=True))

        with self.engine.connect() as connection:
            rows = connection.execute(query, params).mappings().all()

        return [self._developer_from_row(row, terms, self.currency) for row in rows]

    def count_freelancers(
        self,
        skills: list[str],
        project_type: str | None = None,
        min_experience_years: float | None = None,
    ) -> int:
        terms = _safe_terms(skills)
        if not terms and project_type:
            terms = _safe_terms([project_type])
        if not terms:
            return 0

        predicates: list[str] = []
        params: dict[str, object] = {}
        for index, term in enumerate(terms):
            key = f"count_term_{index}"
            predicates.append(
                f"(LOWER(COALESCE(f.Skills, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.SearchTags, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.GigTitle, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.Description, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(p.BasicDesc, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(p.StandardDesc, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(p.PremiumDesc, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(c.CategoryDesc, '')) LIKE :{key})"
            )
            params[key] = f"%{term}%"
        match_score = " + ".join(
            f"MAX(CASE WHEN {predicate} THEN 1 ELSE 0 END)"
            for predicate in predicates
        )
        minimum_matches = max(1, ceil(len(terms) * 0.5))
        params["minimum_matches"] = minimum_matches
        query = text(
            f"""
            SELECT COUNT(*) AS MatchCount
            FROM (
                SELECT f.UserID
                FROM AIADVISOR.Freelancers AS f
                LEFT JOIN AIADVISOR.Gigs AS g ON g.Userid = f.UserID
                LEFT JOIN AIADVISOR.GigPrices AS p ON p.GigID = g.GigID
                LEFT JOIN AIADVISOR.Categories AS c ON c.CategoryID = g.CategoryID
                WHERE {" OR ".join(predicates)}
                GROUP BY f.UserID
                HAVING ({match_score}) >= :minimum_matches
            ) AS MatchingFreelancers
            """
        )
        with self.engine.connect() as connection:
            return int(connection.execute(query, params).scalar_one())

    @staticmethod
    def _developer_from_row(
        row: RowMapping,
        terms: list[str],
        currency: str = "USD",
    ) -> DeveloperMatch:
        matched = [
            term for index, term in enumerate(terms) if int(row[f"Match{index}"] or 0)
        ]
        rating = float(row["AvgRatings"]) if row["AvgRatings"] is not None else None
        reviews = int(row["NumberOfReviews"] or 0)
        gigs = int(row["GigCount"] or 0)
        match_count = int(row["SkillMatchCount"] or 0)
        coverage_percent = round(match_count / len(terms) * 100) if terms else 0
        score = (
            coverage_percent
            + (rating or 0) * 2
            + min(reviews, 100) / 20
            + min(gigs, 20) / 10
        )
        source_labels = {
            "profile_skills": "profile skills",
            "gig_title": "gig title",
            "search_tags": "search tags",
            "gig_description": "gig description",
            "package_description": "package description",
            "category": "category",
        }
        evidence = {
            term: [
                label
                for source, label in source_labels.items()
                if int(row.get(f"Evidence{index}_{source}", 0) or 0)
            ]
            for index, term in enumerate(terms)
            if int(row[f"Match{index}"] or 0)
        }
        return DeveloperMatch(
            user_id=int(row["UserID"]),
            display_name=str(row["DisplayName"]),
            profile_picture=(
                str(row["ProfilePicture"])
                if row.get("ProfilePicture")
                else None
            ),
            skills=str(row["Skills"]),
            level=row["Level"],
            rating=rating,
            review_count=reviews,
            matched_tech=matched,
            requested_tech_count=len(terms),
            coverage_percent=coverage_percent,
            gig_count=gigs,
            score=round(score, 2),
            match_evidence=evidence,
            advertised_price_low=(
                float(row["AdvertisedPriceLow"])
                if row.get("AdvertisedPriceLow") is not None
                else None
            ),
            advertised_price_high=(
                float(row["AdvertisedPriceHigh"])
                if row.get("AdvertisedPriceHigh") is not None
                else None
            ),
            price_currency=currency,
        )

    def estimate_cost(
        self,
        technologies: list[str],
        project_type: str | None,
    ) -> Estimate | None:
        rows = self._matching_gig_rows(technologies, project_type)
        values = sorted(
            value
            for row in rows
            if (
                value := self._representative_value(
                    row["BasicPrice"],
                    row["StandardPrice"],
                    row["PremiumPrice"],
                )
            )
            is not None
        )
        return self._estimate_from_rows(
            values,
            rows,
            len(_safe_terms(technologies)),
            self.currency,
            "related marketplace gigs",
        )

    def estimate_time(
        self,
        technologies: list[str],
        project_type: str | None,
    ) -> Estimate | None:
        rows = self._matching_gig_rows(technologies, project_type)
        values = sorted(
            value
            for row in rows
            if (
                value := self._representative_value(
                    row["BasicDeliveryDate"],
                    row["StandardDeliveryDate"],
                    row["PremiumDeliveryDate"],
                )
            )
            is not None
        )
        return self._estimate_from_rows(
            values,
            rows,
            len(_safe_terms(technologies)),
            "days",
            "related marketplace gigs",
        )

    @staticmethod
    def _representative_value(*raw_values: object) -> float | None:
        values = [
            float(value)
            for value in raw_values
            if value is not None and float(value) > 0
        ]
        return statistics.median(values) if values else None

    @staticmethod
    def _estimate(
        values: list[float],
        unit: str,
        source: str,
        relevance: str = "medium",
    ) -> Estimate | None:
        if not values:
            return None
        data_volume = _confidence(len(values))
        return Estimate(
            low=round(_percentile(values, 0.25), 2),
            median=round(statistics.median(values), 2),
            high=round(_percentile(values, 0.75), 2),
            sample_size=len(values),
            confidence=_overall_confidence(len(values), relevance),
            data_volume=data_volume,
            relevance=relevance,
            unit=unit,
            source=source,
        )

    @classmethod
    def _estimate_from_rows(
        cls,
        values: list[float],
        rows: list[RowMapping],
        technology_count: int,
        unit: str,
        source: str,
    ) -> Estimate | None:
        if not rows:
            return None
        if technology_count:
            coverage_ratio = sum(
                int(row["TechMatchCount"] or 0) / technology_count for row in rows
            ) / len(rows)
        else:
            coverage_ratio = 0
        project_match = any(int(row["ProjectMatchCount"] or 0) > 0 for row in rows)
        relevance = _relevance_label(coverage_ratio, project_match)
        return cls._estimate(values, unit, source, relevance)

    def _matching_gig_rows(
        self,
        technologies: list[str],
        project_type: str | None,
    ) -> list[RowMapping]:
        technology_terms = _safe_terms(technologies)
        project_terms = _project_terms(project_type)
        if not technology_terms and not project_terms:
            return []

        technology_predicates: list[str] = []
        project_predicates: list[str] = []
        params: dict[str, str] = {}
        for index, term in enumerate(technology_terms):
            key = f"tech_{index}"
            technology_predicates.append(
                f"(LOWER(COALESCE(g.GigTitle, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.SearchTags, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.Description, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(c.CategoryDesc, '')) LIKE :{key})"
            )
            params[key] = f"%{term}%"

        for index, term in enumerate(project_terms):
            key = f"project_{index}"
            project_predicates.append(
                f"(LOWER(COALESCE(g.GigTitle, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.SearchTags, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(g.Description, '')) LIKE :{key} "
                f"OR LOWER(COALESCE(c.CategoryDesc, '')) LIKE :{key})"
            )
            params[key] = f"%{term}%"

        tech_match = (
            " + ".join(
                f"CASE WHEN {predicate} THEN 1 ELSE 0 END"
                for predicate in technology_predicates
            )
            or "0"
        )
        project_match = (
            " + ".join(
                f"CASE WHEN {predicate} THEN 1 ELSE 0 END"
                for predicate in project_predicates
            )
            or "0"
        )
        if technology_terms:
            minimum_coverage = max(1, ceil(len(technology_terms) * 0.6))
            where_clause = f"({tech_match}) > 0"
        else:
            where_clause = f"({project_match}) > 0"

        query = text(
            f"""
            SELECT
                g.GigID,
                p.BasicPrice, p.StandardPrice, p.PremiumPrice,
                p.BasicDeliveryDate, p.StandardDeliveryDate, p.PremiumDeliveryDate,
                ({tech_match}) AS TechMatchCount,
                ({project_match}) AS ProjectMatchCount
            FROM AIADVISOR.Gigs AS g
            JOIN AIADVISOR.GigPrices AS p ON p.GigID = g.GigID
            LEFT JOIN AIADVISOR.Categories AS c ON c.CategoryID = g.CategoryID
            WHERE {where_clause}
            """
        )
        with self.engine.connect() as connection:
            rows = list(connection.execute(query, params).mappings().all())

        if technology_terms and rows:
            strongest_match = max(int(row["TechMatchCount"] or 0) for row in rows)
            accepted_coverage = (
                minimum_coverage
                if strongest_match >= minimum_coverage
                else strongest_match
            )
            rows = [
                row
                for row in rows
                if int(row["TechMatchCount"] or 0) >= accepted_coverage
            ]

        # Prefer project-specific rows when they exist. Otherwise retain the
        # technology matches but lower the relevance label in the estimate.
        project_rows = [
            row for row in rows if int(row["ProjectMatchCount"] or 0) > 0
        ]
        return project_rows or rows
