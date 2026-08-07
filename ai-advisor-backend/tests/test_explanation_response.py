from app.schemas import ChatContext, ChatData, ExtractedSlots, Intent
from app.templates import build_response


def test_elaboration_uses_advisory_response_without_repeating_stack() -> None:
    slots = ExtractedSlots(
        intents=[Intent.EXPLAIN_PROJECT],
        project_type="electrical products online store",
        suggested_tech=["shopify"],
        advisory_response=(
            "The store should organize electrical products into searchable "
            "categories, with product pages, a cart, checkout, and order tracking."
        ),
    )

    response = build_response(
        slots,
        ChatContext(
            project_type="electrical products online store",
            suggested_tech=["shopify"],
        ),
        ChatData(technology_used=["shopify"]),
    )

    assert "searchable categories" in response
    assert "Suggested technology" not in response
