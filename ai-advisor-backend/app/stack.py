from collections.abc import Iterable


def normalize_suggested_stack(
    project_type: str | None,
    technologies: Iterable[str],
) -> list[str]:
    """Enforce a coherent minimal architecture for known managed platforms."""
    normalized = list(dict.fromkeys(technology.strip().lower() for technology in technologies))
    project = (project_type or "").lower()

    if "shopify" in normalized:
        custom_indicators = {
            "headless",
            "custom storefront",
            "custom checkout",
            "custom backend",
            "marketplace",
        }
        if not any(indicator in project for indicator in custom_indicators):
            # Shopify owns the commerce backend and database for a standard
            # store. Liquid is an implementation detail, not a separate
            # architecture component for marketplace matching.
            return ["shopify"]

    return normalized

