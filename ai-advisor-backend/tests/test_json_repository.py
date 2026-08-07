import json

from app.json_repository import JsonCandidateRepository


def test_json_repository_matches_skills_without_retaining_contact_data(tmp_path) -> None:
    source = tmp_path / "candidates.json"
    source.write_text(
        json.dumps(
            [
                {
                    "name": "Candidate",
                    "skills": "React.js | Node Js | PostgreSQL",
                    "summary": "Full stack developer",
                    "experience": "3y",
                    "price": "6 Lacs",
                    "email": "private@example.com",
                    "phone": "1234567890",
                }
            ]
        ),
        encoding="utf-8",
    )
    repository = JsonCandidateRepository(str(source))

    matches = repository.find_developers(["react", "node.js"], None, 5)

    assert repository.profile_count == 1
    assert matches[0].coverage_percent == 100
    assert matches[0].compensation_label == "6 Lacs"
    assert matches[0].annual_compensation_inr == 600_000
    assert matches[0].daily_rate_inr == 4_200
    assert matches[0].hourly_rate_inr == 525
    assert "email" not in repository._profiles[0]
    assert "phone" not in repository._profiles[0]


def test_json_repository_leaves_missing_compensation_rates_empty(tmp_path) -> None:
    source = tmp_path / "candidates.json"
    source.write_text(
        json.dumps([{"name": "Candidate", "skills": "React", "price": None}]),
        encoding="utf-8",
    )

    match = JsonCandidateRepository(str(source)).find_developers(["react"], None, 1)[0]

    assert match.annual_compensation_inr is None
    assert match.daily_rate_inr is None
    assert match.hourly_rate_inr is None


def test_json_repository_counts_candidates_with_at_least_half_coverage(tmp_path) -> None:
    source = tmp_path / "candidates.json"
    source.write_text(
        json.dumps(
            [
                {"name": "Full", "skills": "React | Node JS"},
                {"name": "Half", "skills": "React"},
                {"name": "None", "skills": "Python"},
            ]
        ),
        encoding="utf-8",
    )
    repository = JsonCandidateRepository(str(source))

    assert repository.count_freelancers(["react", "node.js"]) == 2


def test_json_repository_applies_minimum_total_experience(tmp_path) -> None:
    source = tmp_path / "candidates.json"
    source.write_text(
        json.dumps(
            [
                {"name": "Junior", "skills": ".NET Framework", "experience": "1y 11m"},
                {"name": "Eligible", "skills": ".NET Framework", "experience": "2y 0m"},
            ]
        ),
        encoding="utf-8",
    )
    repository = JsonCandidateRepository(str(source))

    matches = repository.find_developers([".net framework"], None, 5, 2)

    assert [match.display_name for match in matches] == ["Eligible"]


def test_json_repository_orders_equal_matches_by_most_experience(tmp_path) -> None:
    source = tmp_path / "candidates.json"
    source.write_text(
        json.dumps(
            [
                {"name": "Less experienced", "skills": "React", "experience": "2y"},
                {"name": "Most experienced", "skills": "React", "experience": "8y 6m"},
                {"name": "Middle", "skills": "React", "experience": "5y"},
            ]
        ),
        encoding="utf-8",
    )

    matches = JsonCandidateRepository(str(source)).find_developers(["react"], None, 5)

    assert [match.display_name for match in matches] == [
        "Most experienced",
        "Middle",
        "Less experienced",
    ]
