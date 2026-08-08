from app.repository import (
    AdvisorRepository,
    _confidence,
    _overall_confidence,
    _percentile,
    _project_terms,
    _relevance_label,
    _safe_terms,
)


def test_percentile_interpolates() -> None:
    assert _percentile([10, 20, 30, 40], 0.25) == 17.5
    assert _percentile([10], 0.75) == 10


def test_confidence_uses_sample_size() -> None:
    assert _confidence(5) == "low"
    assert _confidence(10) == "medium"
    assert _confidence(30) == "high"
    assert _overall_confidence(30, "high") == "high"
    assert _overall_confidence(30, "low") == "low"


def test_project_terms_remove_generic_words() -> None:
    assert _project_terms("a website for my textile business") == ["textile"]


def test_skill_separators_are_normalized_without_collapsing_words() -> None:
    assert _safe_terms(["UI/UX Design"]) == ["ui ux design"]


def test_relevance_requires_project_and_stack_coverage_for_high() -> None:
    assert _relevance_label(1.0, True) == "high"
    assert _relevance_label(1.0, False) == "medium"
    assert _relevance_label(0.4, True) == "low"


def test_estimate_uses_median_and_iqr() -> None:
    estimate = AdvisorRepository._estimate(
        [10, 20, 30, 1000],
        "USD",
        "test data",
    )

    assert estimate is not None
    assert estimate.low == 17.5
    assert estimate.median == 25
    assert estimate.high == 272.5
    assert estimate.sample_size == 4
    assert estimate.confidence == "low"
    assert estimate.data_volume == "low"
    assert estimate.relevance == "medium"


def test_representative_value_uses_one_median_per_gig() -> None:
    assert AdvisorRepository._representative_value(10, 50, 100) == 50
    assert AdvisorRepository._representative_value(None, 20, None) == 20


def test_developer_match_records_where_skill_evidence_was_found() -> None:
    row = {
        "UserID": 51,
        "DisplayName": "Pankaj",
        "Skills": "Software Developer",
        "Level": None,
        "AvgRatings": 4.5,
        "NumberOfReviews": 3,
        "GigCount": 1,
        "SkillMatchCount": 1,
        "Match0": 1,
        "Evidence0_profile_skills": 0,
        "Evidence0_gig_title": 0,
        "Evidence0_search_tags": 0,
        "Evidence0_gig_description": 1,
        "Evidence0_package_description": 0,
        "Evidence0_category": 0,
    }

    match = AdvisorRepository._developer_from_row(row, ["python"])

    assert match.matched_tech == ["python"]
    assert match.match_evidence == {"python": ["gig description"]}
