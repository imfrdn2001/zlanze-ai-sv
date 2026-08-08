from app.schemas import (
    ChatContext,
    ChatData,
    DeveloperMatch,
    Estimate,
    ExtractedSlots,
    Intent,
)
from app.templates import build_response


def test_combined_response_contains_requested_sections() -> None:
    slots = ExtractedSlots(
        intents=[
            Intent.FIND_DEVELOPER,
            Intent.ESTIMATE_COST,
            Intent.ESTIMATE_TIME,
            Intent.SUGGEST_TECHNOLOGY,
        ],
        project_type="web application",
        suggested_tech=["react", "fastapi"],
    )
    context = ChatContext(project_type="web application", budget=100)
    data = ChatData(
        technology_used=["react", "fastapi"],
        developers=[
            DeveloperMatch(
                user_id=1,
                display_name="Developer",
                skills="React, FastAPI",
                rating=4.8,
                review_count=8,
                matched_tech=["react", "fastapi"],
                requested_tech_count=2,
                coverage_percent=100,
                gig_count=2,
                score=11.4,
            )
        ],
        cost=Estimate(
            low=150,
            median=250,
            high=400,
            sample_size=20,
            confidence="medium",
            data_volume="medium",
            relevance="medium",
            unit="USD",
            source="related marketplace gigs",
        ),
        time=Estimate(
            low=3,
            median=5,
            high=8,
            sample_size=12,
            confidence="medium",
            data_volume="medium",
            relevance="medium",
            unit="days",
            source="related marketplace gigs",
        ),
    )

    response = build_response(slots, context, data)

    assert "Suggested technology: react, fastapi" in response
    assert "Top recommended" in response
    assert "Estimated marketplace price" in response
    assert "Estimated delivery time" in response
    assert "budget is below" in response


def test_cost_follow_up_does_not_repeat_technology() -> None:
    slots = ExtractedSlots(
        intents=[Intent.ESTIMATE_COST],
        project_type="ecommerce store",
        suggested_tech=["shopify"],
    )
    data = ChatData(
        technology_used=["shopify"],
        cost=Estimate(
            low=50,
            median=100,
            high=200,
            sample_size=18,
            confidence="medium",
            data_volume="medium",
            relevance="high",
            unit="USD",
            source="related marketplace gigs",
        ),
    )

    response = build_response(slots, ChatContext(), data)

    assert "Suggested technology" not in response
    assert "$50–$200" in response
    assert "18 related gigs" in response


def test_clarification_short_circuits_results() -> None:
    slots = ExtractedSlots(
        intents=[Intent.FIND_DEVELOPER],
        needs_clarification=True,
        clarification_question="What would you like to build?",
    )

    assert (
        build_response(slots, ChatContext(), ChatData())
        == "What would you like to build?"
    )


def test_partial_stack_results_are_disclosed() -> None:
    slots = ExtractedSlots(
        intents=[Intent.FIND_DEVELOPER],
        suggested_tech=["react", "node.js", "postgresql"],
    )
    data = ChatData(
        technology_used=slots.suggested_tech,
        developers=[
            DeveloperMatch(
                user_id=1,
                display_name="Partial Developer",
                skills="React, Node.js",
                matched_tech=["react", "node.js"],
                requested_tech_count=3,
                coverage_percent=67,
                score=70,
            )
        ],
    )

    response = build_response(slots, ChatContext(), data)

    assert "No freelancer matched the complete stack" in response
    assert "Strong partial matches" in response
    assert "Talent matching for: react, node.js, postgresql" in response
    assert "2/3 stack coverage" in response


def test_complete_matches_are_listed_before_half_stack_matches() -> None:
    slots = ExtractedSlots(
        intents=[Intent.FIND_DEVELOPER],
        suggested_tech=["react", "node.js"],
    )
    complete = DeveloperMatch(
        user_id=1,
        display_name="Complete Developer",
        skills="React, Node.js",
        matched_tech=["react", "node.js"],
        requested_tech_count=2,
        coverage_percent=100,
        score=100,
    )
    partial = DeveloperMatch(
        user_id=2,
        display_name="Partial Developer",
        skills="React",
        matched_tech=["react"],
        requested_tech_count=2,
        coverage_percent=50,
        score=50,
    )

    response = build_response(
        slots,
        ChatContext(),
        ChatData(
            technology_used=slots.suggested_tech,
            developers=[partial, complete],
        ),
    )

    assert response.index("Complete Developer") < response.index("Partial Developer")
    assert "Strong partial matches — at least half of the stack" in response


def test_talent_count_and_design_matches_are_supported() -> None:
    slots = ExtractedSlots(
        intents=[Intent.COUNT_TALENT, Intent.FIND_DEVELOPER],
        required_skills=["ui/ux design"],
    )
    designer = DeveloperMatch(
        user_id=3,
        display_name="Designer",
        skills="UI/UX Design",
        matched_tech=["ui/ux design"],
        requested_tech_count=1,
        coverage_percent=100,
        score=100,
    )

    response = build_response(
        slots,
        ChatContext(required_skills=["ui/ux design"]),
        ChatData(
            search_terms=["ui/ux design"],
            total_matches=12,
            developers=[designer],
        ),
    )

    assert "12 freelancers match ui/ux design" in response
    assert "Talent matching for: ui/ux design" in response
    assert "Designer" in response
