from app.schemas import ExtractedSlots, Intent


SCOPED_PROJECT_MARKERS = {
    "booking",
    "brochure",
    "catalog",
    "catalogue",
    "ecommerce",
    "e-commerce",
    "informational",
    "lead generation",
    "marketplace",
    "online store",
    "portal",
    "shopping cart",
}

COMPARISON_REFERENCES = {
    "all",
    "all three",
    "each",
    "each one",
    "these",
    "these options",
    "three options",
    "3 options",
    "both",
}


def requests_all_pending_options(query: str, pending_clarification: str | None) -> bool:
    """Recognize a request to evaluate the choices offered in the prior turn."""
    if not pending_clarification:
        return False
    normalized = " ".join(query.lower().split())
    refers_to_choices = any(reference in normalized for reference in COMPARISON_REFERENCES)
    asks_for_results = any(
        term in normalized
        for term in ("developer", "freelancer", "cost", "price", "suggest", "compare")
    )
    return refers_to_choices and asks_for_results


def enforce_scope_clarification(
    slots: ExtractedSlots,
    has_pending_intents: bool,
) -> ExtractedSlots:
    """Prevent stack/matching decisions for an unspecified business website."""
    if has_pending_intents or slots.needs_clarification:
        return slots

    project_type = (slots.project_type or "").lower()
    relevant_intents = {
        Intent.FIND_DEVELOPER,
        Intent.ESTIMATE_COST,
        Intent.ESTIMATE_TIME,
        Intent.SUGGEST_TECHNOLOGY,
    }
    is_unscoped_website = (
        "website" in project_type
        and not any(marker in project_type for marker in SCOPED_PROJECT_MARKERS)
    )
    if not is_unscoped_website or not relevant_intents.intersection(slots.intents):
        return slots

    domain = project_type.replace("website", "").strip() or "business"
    return slots.model_copy(
        update={
            "needs_clarification": True,
            "clarification_question": (
                f"Should this {domain} website be an informational presence, "
                "a lead-generation or service-booking site, or an online store "
                "with a catalogue and checkout?"
            ),
        }
    )
