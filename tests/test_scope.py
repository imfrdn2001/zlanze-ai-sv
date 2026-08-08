from app.scope import enforce_scope_clarification
from app.schemas import ExtractedSlots, Intent


def test_unspecified_business_website_requires_scope() -> None:
    slots = ExtractedSlots(
        intents=[Intent.SUGGEST_TECHNOLOGY, Intent.FIND_DEVELOPER],
        project_type="electric business website",
        suggested_tech=["wordpress", "php", "mysql"],
    )

    result = enforce_scope_clarification(slots, has_pending_intents=False)

    assert result.needs_clarification is True
    assert "online store" in (result.clarification_question or "")


def test_scoped_online_store_does_not_ask_again() -> None:
    slots = ExtractedSlots(
        intents=[Intent.SUGGEST_TECHNOLOGY],
        project_type="electric business online store",
        suggested_tech=["shopify"],
    )

    result = enforce_scope_clarification(slots, has_pending_intents=False)

    assert result.needs_clarification is False

